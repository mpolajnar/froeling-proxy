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

import sys
import argparse

import froeling_proxy
from froeling_lib.__init__ import Froeling, ConnectionInitializationError

parser = argparse.ArgumentParser(description="Proxy for serial communication with Fröling boilers.")
parser.add_argument("tty", help="TTY device of serial port")
parser.add_argument("--port", "-p", help="TCP port to open for inbound requests", type=int)
parser.add_argument("--state", "-s", help="request and print current boiler state", action="store_true")
parser.add_argument("--values", help="request and print temperature values", action="store_true")
args = parser.parse_args()

try:
    froeling = Froeling(args.tty)
except ConnectionInitializationError as e:
    sys.stderr.write("Error connecting to TTY device: {}\n".format(e))
    sys.exit(1)

if args.state:
    state = froeling_proxy.read_state(froeling)
    print("STATE: " + state.hex())
    print("\n".join(state[2:].decode("iso-8859-1").split(";")))

if args.values:
    value_catalog = [
        ("Boiler temperature (Kesseltemperatur)", [0x00, 0x00]),
        ("Exhaust temperature (Abgastemperatur)", [0x00, 0x01]),
        ("External temperature (Außentemperatur)", [0x00, 0x04]),
        ("Buffer top temperature (Puffer 1 oben)", [0x00, 0x76]),
        ("Buffer bottom temperature (Puffer 1 unten)", [0x00, 0x78]),
        ("Hot water storage temperature (Boilertemperatur 1)", [0x00, 0x5d])
    ]
    values = froeling_proxy.read_values(froeling, [byte for entry in value_catalog for byte in entry[1]])
    print("VALUES: " + values.hex())
    for ((label, _), b1, b2) in zip(value_catalog, values[::2], values[1::2]):
        print(label + ": " + froeling_proxy.format_temperature([b1, b2]))

if args.port:
    froeling_proxy.FroelingProxyServer(args.port, froeling).start()