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

from serial import Serial, SerialException


class ConnectionInitializationError(Exception):
    pass


class SerialPortIOError(Exception):
    pass


class ResponseReadError(Exception):
    pass


class NoResponseError(ResponseReadError):
    pass


class WrongResponseHeaderError(ResponseReadError):
    """
    :param response: bytes received
    """
    def __init__(self, response):
        super(WrongResponseHeaderError, self).__init__("Received: " + response.hex())


class WrongResponseCRCError(ResponseReadError):
    def __init__(self, expected_crc, actual_crc):
        super(WrongResponseCRCError, self).__init__("Expected CRC value {:02X}, received {:02X}".format(expected_crc, actual_crc))


class WrongCommandInResponse(ResponseReadError):
    def __init__(self, expected_cmd, actual_cmd):
        super(WrongCommandInResponse, self).__init__("Expected command {:02X}, received {:02X}".format(expected_cmd, actual_cmd))


class IncompleteResponseError(ResponseReadError):
    def __init__(self, declared_len, actual_len):
        super(IncompleteResponseError, self).__init__("Expected {} bytes after frame header, received {}".format(declared_len, actual_len))


class Froeling:
    """
    A connection to a Fröling boiler via a serial link.

    Constructor initializes a Froeling object with given TTY that can either be a string with TTY device name
    or an object providing read, write and reset_input_buffer like pyserial's Serial class does.

    :param tty: TTY device file name string, or a Serial-like object
    :param ignore_crc: ignore CRC on received messages; accept response and do not throw
        :py:class:`froeling_lib.WrongResponseCRCError`; default is True because experiments have shown that S4 Turbo
        apparently sometimes computes the CRC wrongly as in the following example response
        that could be reproduced over and over again: `02fd000330fffe00` (should be `84` instead of `00`)
    :raise ConnectionInitializationError: problem setting up the serial port
    """
    BLOCK_START = bytes([0x02, 0xfd])

    def __init__(self, tty, ignore_crc=True):
        if hasattr(tty, "write") and hasattr(tty, "read") and hasattr(tty, "reset_input_buffer"):
            self.port = tty
        else:
            try:
                self.port = Serial(tty, 57600, timeout=1)
            except SerialException as e:
                raise ConnectionInitializationError(e)
        self.ignore_crc = ignore_crc

    def send_command(self, command, *parameters):
        """
        Send the given command (one byte) and parameters (a list of objects like bytes or lists of ints)
        via serial interface and return response (bytes object). Note that the frame header (02fd) and
        message length are prepended and a checksum is appended to the request. Likewise, the frame header,
        message length AND COMMAND are stripped from the beginning of the response, and the checksum is
        likewise not returned.

        :param command: command (Befehl) to send via interface (int, list of ints of length 1, bytes
            object of length 1...)
        :param parameters: command parameters to send via interface (list of ints, bytes object...)
        :return: bytes object with response payload stripped of frame envelope and command byte
        :raise SerialPortIOError: I/O error on writing to or reading from the serial port
        :raise NoResponseError: no response was received on serial port within 1 second
        :raise WrongResponseHeaderError: received data did not begin with bytes 0x02FD or less than 4
            bytes were received
        :raise IncompleteResponseError: within 1 second, less than the number of bytes declared
            in the header were received
        :raise WrongResponseCRCError: the last received byte did not contain a correct CRC value
        :raise WrongCommandInResponse: the command in received response did not match the one in
            the request sent
        """
        message = bytes(command) if hasattr(command, "__iter__") else bytes([command]) + \
                                                                      bytes([value for parameter in parameters for value in parameter])
        frame = Froeling.BLOCK_START + len(message).to_bytes(2, "big") + message
        frame_and_crc = frame + bytes([_compute_crc(frame)])

        self.port.reset_input_buffer()
        try:
            self.port.write(bytes(frame_and_crc))
            response_header = self.port.read(4)
        except Exception as e:
            raise SerialPortIOError(e)

        if len(response_header) == 0:
            raise NoResponseError()

        if len(response_header) < 4 or response_header[0:2] != bytes([0x02, 0xfd]):
            raise WrongResponseHeaderError(response_header)

        try:
            response_len = 1 + int.from_bytes(response_header[2:4], "big")
            response = self.port.read(response_len)
        except Exception as e:
            raise SerialPortIOError(e)

        if len(response) < response_len:
            raise IncompleteResponseError(response_len, len(response))
        expected_crc = _compute_crc(response_header + response[:-1])
        if expected_crc != response[-1] and not self.ignore_crc:
            raise WrongResponseCRCError(expected_crc, response[-1])
        if response[0] != message[0]:
            raise WrongCommandInResponse(message[0], response[0])
        return response[1:-1]  # Skip command ("Befehl") and CRC


def _compute_crc(frame):
    """
    :param frame: iterable of bytes from which to compute CRC
    :return: CRC value (int between 0 and 255)
    """
    crc = 0
    for byte in frame:
        crc = (crc ^ byte ^ (byte * 2 & 0xff)) & 0xff
    return crc
