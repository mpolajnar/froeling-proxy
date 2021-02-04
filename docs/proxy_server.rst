Usage of Fröling Proxy Server
=============================

By invoking the Proxy Server, you can use the TCP socket it opens to exchange the data
with the boiler in a (somewhat) human-readable format, i.e. hexadecimal representation
of the bytes sent and received.

Using the `-h` flag, usage pattern can be obtained:

.. code-block:: console

    $ python froeling_proxy -h                                                                                                                                   2 master!+?
    usage: froeling_proxy [-h] [--port PORT] [--state] [--values] tty

    Proxy for serial communication with Fröling boilers.

    positional arguments:
      tty                   TTY device of serial port

    optional arguments:
      -h, --help            show this help message and exit
      --port PORT, -p PORT  TCP port to open for inbound requests
      --state, -s           request and print current boiler state
      --values              request and print temperature values

This is an example of exchanging data via the Proxy Server using the `netcat` (`nc`)
program for TCP socket communication:

.. code-block:: console
    :linenos:

    # start proxy in the background on port 1090
    $ python3 froeling_proxy.py -p 1090 /dev/ttyUSB0 &

    $ nc localhost 1090
    51
    000557696e746572626574726965623b466575657220417573
    300004
    000b

Lines 6 and 8 are responses from the boiler, denoting that it is in the winter mode and
that fire has gone out (line 6, if decoded to ASCII), and that outside there is 5.5 degrees Celsius
(line 8 if decoded as a signed 16-bit integer and divided by 2).