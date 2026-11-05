"""
가상 보드 테스트.  실행:  python -m unittest discover tests
"""
import time
import unittest

from mock import protocol
from mock.main_board import (KEY_START, SCREEN_CONFIRM, SCREEN_FINISH, SCREEN_MOOD_SELECT,
                             SCREEN_START, decode_mood_from_touch, mood_to_touch)
from mock.system import create_virtual_system


class ProtocolTests(unittest.TestCase):
    def test_job_packet_matches_c_struct(self):
        packet = protocol.build_job_packet(121, 3, 2.0)
        self.assertEqual(len(packet), 9)  # 1 + sizeof(int) + sizeof(float)
        self.assertEqual(packet[0], 121)
        self.assertEqual(protocol.parse_job_packet(packet), (3, 2.0))

    def test_done_packet(self):
        self.assertTrue(protocol.is_done_packet(protocol.build_done_packet(121), 121))
        self.assertFalse(protocol.is_done_packet(protocol.build_done_packet(20), 121))

    def test_touch_keys_roundtrip(self):
        for mood in range(1, 9):
            self.assertEqual(decode_mood_from_touch(mood_to_touch(mood)), mood)


def wait(pred, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


class VirtualSystemTests(unittest.TestCase):
    def make(self, **kw):
        return create_virtual_system(speed=200, show_lcd=False, out=lambda *_: None, **kw)

    def drain_serial(self, system):
        lines = []
        while True:
            raw = system.serial.readline() if not system.serial._lines.empty() else b""
            if not raw:
                return lines
            lines.append(raw.decode().strip())

    def make_perfume(self, system, mood):
        board, lcd = system.main_board, system.lcd
        self.assertTrue(wait(lambda: board.current_state == SCREEN_START and not board.needs_redraw))
        lcd.press(0x01)
        self.assertTrue(wait(lambda: board.current_state == SCREEN_MOOD_SELECT))
        lcd.press(mood_to_touch(mood))
        self.assertTrue(wait(lambda: board.current_state == SCREEN_CONFIRM))
        lcd.press(KEY_START)

    def test_full_blend(self):
        system = self.make()
        self.make_perfume(system, 2)  # Calm: 8, 4, 2, 2
        self.assertTrue(wait(lambda: system.main_board.current_state == SCREEN_FINISH))
        self.assertEqual(system.tanks.levels, {1: 22, 2: 26, 3: 28, 4: 28})
        lines = self.drain_serial(system)
        self.assertIn("MOOD : 2", lines)
        self.assertIn("PERFUME : Lavender : 8", lines)
        self.assertIn("STATUS : SCREEN_FINISH", lines)

    def test_shortage_stops_blend(self):
        system = self.make()
        system.tanks.drain(3)
        self.make_perfume(system, 4)  # Sweet 은 Vanilla 8ml 필요
        self.assertTrue(wait(lambda: system.main_board.current_state == SCREEN_MOOD_SELECT))
        lines = self.drain_serial(system)
        self.assertIn("WATER_X : 3", lines)
        self.assertFalse(any(l.startswith("PERFUME") for l in lines))


if __name__ == "__main__":
    unittest.main()
