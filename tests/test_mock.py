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

    def test_reply_packets(self):
        done = protocol.build_done_packet(121, protocol.LEVEL_OK)
        self.assertEqual(done, bytes([121]) + b"DONE" + bytes([1]))  # sub-board RunJob() 과 같은 6바이트
        self.assertTrue(protocol.is_done_packet(done, 121))
        self.assertFalse(protocol.is_done_packet(protocol.build_done_packet(20), 121))
        low = protocol.build_low_packet(121, 3)
        self.assertEqual(low, bytes([121]) + b"LOW" + bytes([3]))
        self.assertTrue(protocol.is_low_packet(low, 121))
        self.assertFalse(protocol.is_done_packet(low, 121))

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
        self.assertIn("WATER_O : 1", lines)  # 주입 후 수위 보고

    def test_low_tank_stops_blend_midway(self):
        """서브보드가 LOW 로 거절하면 거기서 멈추고, 그 전 향료는 이미 들어간 상태"""
        system = self.make()
        system.tanks.drain(3)
        self.make_perfume(system, 4)  # Sweet: Lavender 4 → Cedarwood 2 → Vanilla 8(부족) → Bergamot 2
        self.assertTrue(wait(lambda: system.main_board.current_state == SCREEN_MOOD_SELECT
                             and not system.main_board.needs_redraw))
        lines = self.drain_serial(system)
        self.assertIn("PERFUME : Lavender : 4", lines)
        self.assertIn("WATER_X : 3", lines)
        self.assertNotIn("PERFUME : Bergamot : 2", lines)
        self.assertEqual(system.tanks.levels[1], 26)

    def test_refilled_tank_reports_ok(self):
        system = self.make()
        system.tanks.drain(3)
        system.tanks.refill(3)
        self.make_perfume(system, 1)
        self.assertTrue(wait(lambda: system.main_board.current_state == SCREEN_FINISH))
        self.assertIn("WATER_O : 3", self.drain_serial(system))
    def test_level_query_at_start(self):
        """부팅해서 시작 화면이 뜨면 네 통의 수위를 모두 보고"""
        system = self.make()
        system.tanks.drain(4)
        self.assertTrue(wait(lambda: any(l == "WATER_X : 4" for l in self.lines(system))))
        self.assertIn("WATER_O : 2", self.seen)

    def lines(self, system):
        self.seen = getattr(self, "seen", []) + self.drain_serial(system)
        return self.seen


if __name__ == "__main__":
    unittest.main()
