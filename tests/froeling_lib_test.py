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

import unittest
import pytest
import froeling_lib


class MockedTty:
    def __init__(self):
        self.sent_to_boiler = bytes()
        self.answer_from_boiler = bytes()

    def expect_exchange(self, sent_to_boiler, answer_from_boiler):
        self.sent_to_boiler = bytes(sent_to_boiler)
        self.answer_from_boiler = bytes(answer_from_boiler)

    def write(self, data):
        if bytes(data) != self.sent_to_boiler:
            raise AssertionError("Expected\n  {}\nto be sent to boiler, but was\n  {}".format(self.sent_to_boiler.hex(), bytes(data).hex()))

    def read(self, n):
        answer, self.answer_from_boiler = self.answer_from_boiler[:n], self.answer_from_boiler[n:]
        return answer

    def reset_input_buffer(self):
        pass


class FroelingTest(unittest.TestCase):
    def setUp(self):
        self.mocked_tty = MockedTty()
        self.froeling = froeling_lib.Froeling(self.mocked_tty, True)
        self.froeling_crc = froeling_lib.Froeling(self.mocked_tty, False)

    def _test(self, full_request, full_answer, froeling=None):
        self.mocked_tty.expect_exchange(full_request, full_answer)
        answer = (froeling or self.froeling).send_command(full_request[4], full_request[5:-1])
        self.assertEqual(bytes(full_answer)[5:-1], answer)

    def test_send_command_without_parameters_with_nonempty_response(self):
        self._test(
            [0x02, 0xfd, 0x00, 0x01, 0x51, 0xf1],
            [0x02, 0xfd, 0x00, 0x03, 0x51, 0x01, 0x02, 0x03])

    def test_send_command_without_parameters_with_empty_response(self):
        self._test(
            [0x02, 0xfd, 0x00, 0x01, 0x51, 0xf1],
            [0x02, 0xfd, 0x00, 0x01, 0x51, 0x03])

    def test_send_command_without_parameters_with_nonempty_response_with_crc(self):
        with pytest.raises(froeling_lib.WrongResponseCRCError):
            self._test(
                [0x02, 0xfd, 0x00, 0x01, 0x51, 0xf1],
                [0x02, 0xfd, 0x00, 0x03, 0x51, 0x01, 0x02, 0x03],
                self.froeling_crc)
        self._test(
            [0x02, 0xfd, 0x00, 0x01, 0x51, 0xf1],
            [0x02, 0xfd, 0x00, 0x03, 0x51, 0x01, 0x02, 0xf2],
            self.froeling_crc)

    def test_send_command_without_parameters_with_empty_response_with_crc(self):
        with pytest.raises(froeling_lib.WrongResponseCRCError):
            self._test(
                [0x02, 0xfd, 0x00, 0x01, 0x51, 0xf1],
                [0x02, 0xfd, 0x00, 0x01, 0x51, 0x03],
                self.froeling_crc)
        self._test(
            [0x02, 0xfd, 0x00, 0x01, 0x51, 0xf1],
            [0x02, 0xfd, 0x00, 0x01, 0x51, 0xf1],
            self.froeling_crc)

    def test_send_command_wrong_response(self):
        with pytest.raises(froeling_lib.WrongCommandInResponse):
            self._test(
                [0x02, 0xfd, 0x00, 0x01, 0x52, 0xf4],
                [0x02, 0xfd, 0x00, 0x03, 0x51, 0x01, 0x02, 0x03])

    def test_send_command_too_short_response(self):
        with pytest.raises(froeling_lib.ResponseReadError):
            self._test(
                [0x02, 0xfd, 0x00, 0x01, 0x52, 0xf4],
                [0x02, 0xfd, 0x00, 0x05, 0x51, 0x01, 0x02, 0x03])

    def test_send_command_wrong_response_header_1(self):
        with pytest.raises(froeling_lib.WrongResponseHeaderError):
            self._test(
                [0x02, 0xfd, 0x00, 0x01, 0x52, 0xf4],
                [0x02, 0xfd, 0x00])

    def test_send_command_wrong_response_header_2(self):
        with pytest.raises(froeling_lib.WrongResponseHeaderError):
            self._test(
                [0x02, 0xfd, 0x00, 0x01, 0x52, 0xf4],
                [0x03, 0xfd, 0x00, 0x05, 0x51, 0x01, 0x02, 0x03])

    def test_send_command_no_response(self):
        with pytest.raises(froeling_lib.NoResponseError):
            self._test(
                [0x02, 0xfd, 0x00, 0x01, 0x52, 0xf4],
                [])
