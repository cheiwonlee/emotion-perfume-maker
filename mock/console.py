"""
가상 보드를 조작하는 방법 두 가지
  1) 직접 조작 (키보드로 터치 LCD 누르기)
  2) 자동 시연 (--auto) : 터치 → 기분 선택 → Start → 완료 를 계속 반복
"""
import random
import threading
import time

from . import protocol
from .main_board import (KEY_BACK, KEY_START, SCREEN_BLENDING, SCREEN_CONFIRM,
                         SCREEN_FINISH, SCREEN_MOOD_SELECT, SCREEN_START, mood_to_touch)

HELP = """
──────────── 가상 터치 LCD 조작법 ────────────
  t            화면 터치 (START / FINISH 화면에서 다음으로)
  1 ~ 8        기분 선택 (1 Fresh 2 Calm 3 Bold 4 Sweet
                          5 Active 6 Cozy 7 Mystic 8 Random)
  s / b        확인 화면에서 [Start] / [Back]
  m <번호>     기분 하나를 처음부터 끝까지 한 번에 (예: m 2)
  levels       향료 통 잔량 보기
  drain <n>    n번 향료 통 비우기 (1 Lavender 2 Cedarwood 3 Vanilla 4 Bergamot)
  refill       향료 통 전부 채우기
  auto         자동 시연 켜기/끄기
  help / q     도움말 / 종료
──────────────────────────────────────────────
"""


def wait_state(system, states, timeout=600):
    end = time.time() + timeout
    while time.time() < end:
        if system.main_board.current_state in states and not system.main_board.needs_redraw:
            return True
        time.sleep(0.05)
    return False


def run_mood_once(system, mood):
    """START → 기분 선택 → Start → 완료 까지 한 번 실행"""
    board, lcd = system.main_board, system.lcd
    if board.current_state == SCREEN_BLENDING:
        print("이미 제조 중이에요.")
        return
    if board.current_state in (SCREEN_START, SCREEN_FINISH):
        if board.current_state == SCREEN_FINISH:
            lcd.press(1)
            wait_state(system, [SCREEN_START])
        lcd.press(1)
        wait_state(system, [SCREEN_MOOD_SELECT])
    if board.current_state == SCREEN_CONFIRM:
        lcd.press(KEY_BACK)
        wait_state(system, [SCREEN_MOOD_SELECT])
    lcd.press(mood_to_touch(mood))
    wait_state(system, [SCREEN_CONFIRM])
    lcd.press(KEY_START)
    time.sleep(0.5)
    wait_state(system, [SCREEN_FINISH, SCREEN_MOOD_SELECT])


class AutoDemo:
    """기분을 무작위로 골라 계속 제조. 가끔 향료 통을 비웠다가 다시 채워 '부족' 상태도 보여준다."""

    def __init__(self, system):
        self.system = system
        self.running = False

    def toggle(self):
        self.running = not self.running
        if self.running:
            threading.Thread(target=self._loop, daemon=True).start()
        print(f"[AUTO] 자동 시연 {'시작' if self.running else '정지'}")

    def _loop(self):
        cycle = 0
        wait_state(self.system, [SCREEN_START], timeout=30)
        while self.running:
            cycle += 1
            mood = random.randint(1, 8)
            print(f"[AUTO] {cycle}번째 제조 — 기분 {mood} ({protocol.MOOD_NAMES[mood]})")
            run_mood_once(self.system, mood)
            if not self._pause(3):
                return
            if cycle % 3 == 0:  # 세 번에 한 번은 재고 부족 상황을 만든다
                sid = random.randint(1, 4)
                print(f"[AUTO] {protocol.PERFUMES[sid]} 통이 비었어요 (수위 센서 → 부족)")
                self.system.tanks.drain(sid)
                if not self._pause(6):  # 자동 시연을 끄면 비운 상태 그대로 둔다
                    return
                print("[AUTO] 향료 통을 모두 다시 채웠어요")
                self.system.tanks.refill()
                if not self._pause(3):
                    return

    def _pause(self, seconds) -> bool:
        """기다리는 중에 자동 시연이 꺼지면 False"""
        end = time.time() + seconds
        while time.time() < end:
            if not self.running:
                return False
            time.sleep(0.1)
        return self.running


def print_levels(system):
    for sid, name in protocol.PERFUMES.items():
        level = system.tanks.levels[sid]
        bar = "█" * int(level / system.tanks.capacity_ml * 20)
        flag = "부족" if system.tanks.is_low(sid) else "충분"
        print(f"  {sid}. {name:<10} {bar:<20} {level:5.1f}ml  {flag}")


def interactive(system, auto=False):
    demo = AutoDemo(system)
    print(HELP)
    if auto:
        demo.toggle()
    while True:
        try:
            cmd = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            # 입력이 없는 환경(백그라운드 실행 등)에서는 자동 시연만 계속 돌린다
            if demo.running:
                while True:
                    time.sleep(3600)
            return
        if not cmd:
            continue
        parts = cmd.split()
        lcd = system.lcd
        try:
            if cmd in ("q", "quit", "exit"):
                return
            elif cmd in ("h", "help", "?"):
                print(HELP)
            elif cmd == "t":
                lcd.press(1)
            elif cmd.isdigit() and 1 <= int(cmd) <= 8:
                lcd.press(mood_to_touch(int(cmd)))
            elif cmd == "s":
                lcd.press(KEY_START)
            elif cmd == "b":
                lcd.press(KEY_BACK)
            elif parts[0] == "m" and len(parts) == 2:
                threading.Thread(target=run_mood_once, args=(system, int(parts[1])), daemon=True).start()
            elif cmd == "levels":
                print_levels(system)
            elif parts[0] == "drain" and len(parts) == 2:
                system.tanks.drain(int(parts[1]))
                print_levels(system)
            elif cmd == "refill":
                system.tanks.refill()
                print_levels(system)
            elif cmd == "auto":
                demo.toggle()
            else:
                print("알 수 없는 명령이에요. help 를 입력해 보세요.")
        except (ValueError, KeyError):
            print("번호를 확인해 주세요.")
