# Froeling Proxy

This is a library and an application for proxying commands to a Fröling boiler (tried and tested on a Fröling S4 Turbo) via its COM2 interface.

## Library

The library provides a class `Froeling` that takes care of communication frames, including
message length specification and CRC computation, when exchanging commands and
responses with a Fröling boiler.

```python
from froeling_lib import Froeling

# Note that by default the CRC on responses is not validated; see API for details
froeling = Froeling("/dev/ttyS0")   # ttyS0 is the serial port to the boiler
status = froeling.send_command(0x51)
print(status.hex())

some_temperature_values = froeling.send_command(0x30, [0x00, 0x00, 0x00, 0x01])
print(some_temperature_values.hex())
```

## Proxy Server Application

The proxy server application listens to a TCP socket and accepts strings of hexadecimal 
numbers representing commands (without the frame, i.e. the frame initialisation bytes, 
message length declaration and the last CRC byte). Each line is interpreted as one command.
The application responds to the TCP connection with boiler's response in the same encoding,
i.e. strings of hexadecimal numbers, terminated with a newline character. If an error is 
encountered, a line with an exclamation mark followed by description of the error is emitted.

```bash
# start proxy in the background on port 1090
> python3 froeling_proxy.py -p 1090 /dev/ttyUSB0 &

> nc localhost 1090
51
000557696e746572626574726965623b466575657220417573
300004
000b
300004
!WrongResponseHeaderError: Received: 02fd00
```

## Release Notes

* 1.0.3:
  - fix display of exhaust temperature which was too low for a factor of 2
  - improve robustness of the proxy server so that it does not exit due to socket errors
* 1.0.2: First working version
* 1.0.0: Initial release; does not work
* 1.0.1: Attempt to fix the release; does not work
