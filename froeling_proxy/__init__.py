# Copyright 2021 Matija Polajnar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from froeling_lib.__init__ import Froeling, SerialPortIOError, ResponseReadError
try:
    import socket
    import selectors
    import types
except ImportError as ex:
    import sys

    print("Error importing requirements for socket server; it will not work: " + str(ex), file=sys.stderr)

# Commands
CMD_AKTUELLE_WERTE_DES_KESSELS = 0x30
CMD_KESSELZUSTAND_ABFRAGEN = 0x51


def read_state(froeling):
    """
    Send a request for boiler status and return its response.

    :param froeling: proxy object for connection to the boiler (instance of Froeling)
    :return: response from boiler (bytes object)
    """
    return froeling.send_command(CMD_KESSELZUSTAND_ABFRAGEN)


def read_values(froeling, *values):
    """
    Send a request for reading values with given addresses from the boiler and return its response.

    :param froeling: proxy object for connection to the boiler (instance of Froeling)
    :param values: bytes object containing a concatenation of 2-byte addresses of the requested values
    :return: response from boiler (bytes object)
    """
    return froeling.send_command(CMD_AKTUELLE_WERTE_DES_KESSELS, *values)


def format_temperature(value_bytes, multiplied_by_2=True):
    """
    Format the temperature to string with one decimal place and the unit (°C). Assumes the input is
    a bytes object (or compatible, like iterable of ints) with representation of a signed integer with the
    most significant byte first, where the integer is the actual temperature measurement, usually multiplied
    by 2, depending on the value of the second parameter.

    :param value_bytes: bytes with a signed integer that represents the actual temperature in °C,
        usually multiplied by 2 (see next parameter)
    :param multiplied_by_2: determines whether the value represents temperature multiplied by 2 or not
    :return: a string with formatted temperature
    """
    return "{:.1f}°C".format(int.from_bytes(value_bytes, "big", signed=True) / (multiplied_by_2 * 2.0))


class FroelingProxyServer:
    """
    A TCP server that proxies the commands, expressed as strings of hexadecimal representation
    of bytes and separated by a newline (and/or a carriage return character), between the TCP
    socket and a Froeling object, that takes care of the command framing (adding frame header
    including length, and a CRC) and communication with a Fröling boiler over a serial connection.

    This proxy can handle multiple concurrent connections, however, only one command will be issued
    and completed (i.e. its response read) at once.

    If any invalid characters are received (i.e. anything except numbers, lowercase or uppercase
    letters A-F or CR or LF), the connection is hung up immediately.

    Responses from the boiler are also hexadecimal representations of the received bytes, terminated with
    a newline character. In case of a communication error on the serial connection, the error is reported
    back as a UTF-8 string, prepended by an exclamation sign (!).
    """
    VALID_INPUT_BYTES = "\r\n0123456789abcdefABCDEF".encode()

    def __init__(self, port, froeling):
        """
        Constructs a TCP proxy, but does not yet open the socket and start listening.

        :param port: TCP port number to listen on
        :param froeling: the Froeling object used to relay commands to the boiler
        """
        if not isinstance(port, int):
            raise ValueError("port must be an int")
        if not isinstance(froeling, Froeling):
            raise ValueError("froeling must be a Froeling")
        self.port = port
        self.froeling = froeling

    def start(self):
        """
        Starts listening to the TCP port and relaying the commands. It blocks the issuing thread.
        :return: never returns
        """
        self.selector = selectors.DefaultSelector()

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("", self.port))
                s.listen()
                s.setblocking(False)
                self.selector.register(s, selectors.EVENT_READ, data=None)
                while True:
                    events = self.selector.select(timeout=None)
                    for key, mask in events:
                        if key.data is None:
                            self._accept_connection(key.fileobj)
                        else:
                            self._service_connection(key, mask)
        except KeyboardInterrupt:
            pass

    def _accept_connection(self, s):
        try:
            conn, addr = s.accept()
            conn.setblocking(False)
            data = types.SimpleNamespace(addr=addr, inb=b'', outb=b'')
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
            self.selector.register(conn, events, data=data)
        except Exception as e:
            print("Error accepting TCP socket connection: {}".format(e), sys.stderr)
            # noinspection PyBroadException
            self._close_connection(s)

    def _close_connection(self, s):
        # noinspection PyBroadException
        try:
            self.selector.unregister(s)
            s.close()
        except Exception:
            pass

    def _service_connection(self, key, mask):
        s = key.fileobj
        data = key.data

        if mask & selectors.EVENT_READ:
            try:
                recv_data = s.recv(1024)
            except Exception as e:
                print("Error reading from TCP socket: {}".format(e), sys.stderr)
                # noinspection PyBroadException
                self._close_connection(s)
                return
            if recv_data:
                invalid_bytes = [byte for byte in recv_data if byte not in FroelingProxyServer.VALID_INPUT_BYTES]
                if invalid_bytes:
                    print("Bad input bytes " + repr(invalid_bytes) + "; closing connection")
                    self._close_connection(s)
                else:
                    data.inb += recv_data
                    try:
                        self._handle_requests(data)
                    except Exception as e:
                        print("Error handling request: {}".format(e), sys.stderr)
                        # noinspection PyBroadException
                        self._close_connection(s)
                        return
            else:
                self._close_connection(s)

        if mask & selectors.EVENT_WRITE:
            if data.outb:
                try:
                    sent = s.send(data.outb)
                except Exception as e:
                    print("Error writing to TCP socket: {}".format(e), sys.stderr)
                    # noinspection PyBroadException
                    self._close_connection(s)
                    return
                data.outb = data.outb[sent:]

    def _handle_requests(self, data):
        """
        Handle the requests that are received in their entirety from the TCP socket into the data object's
        input buffer (inb). Responses to the issued commands are added to the data's output buffer (outb).

        :param data: the data object of the connection to the socket
        :return: None
        """
        newline_index = next((i for (i, byte) in enumerate(data.inb) if byte in b'\n\r'), None)
        if newline_index is not None:
            try:
                request = bytes.fromhex(data.inb[:newline_index].decode())
            except ValueError as e:
                data.outb += b"!" + (e.__class__.__name__ + ": " + str(e)).encode("UTF-8") + b"\n"
                request = None
            data.inb = data.inb[newline_index + 1:]
            if request:
                try:
                    response = self.froeling.send_command(request[0], request[1:])
                    data.outb += response.hex().encode() + b"\n"
                except (SerialPortIOError, ResponseReadError) as e:
                    data.outb += b"!" + (e.__class__.__name__ + ": " + str(e)).encode("UTF-8") + b"\n"

