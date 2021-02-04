Usage of Fröling Proxy Library
==============================

By importing the :py:class:`froeling_lib.Froeling` class, you can send arbitrary commands to the boiler
and examine the response.

In case you are wondering whether you need a coat or just a light jacket when leaving home, you can
inquire the boiler for outside temperature by using the following example.

.. code-block:: python

   from froeling_lib import Froeling

   froeling = Froeling("/dev/ttyS0")

   response = froeling.send_command(0x30, [0x00, 0x04])

   # Response is a 16-bit (2 byte) signed integer that
   # represents twice the actual temperature
   external_temperature = int.from_bytes(
       response, "big", signed=True) / 2.0

   print("{:.1f}°C".format(external_temperature))