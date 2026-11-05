"""
메인보드(터치 LCD + 회전판 모터 + LoRa 마스터) mock — main-board/Core/Src/main.c 를 옮긴 것.

흐름 (main.c 와 동일)
    START 화면 ─터치→ 기분 선택 ─기분 터치→ 확인 ─[Start]→ 블렌딩 ─완료→ FINISH ─터치→ START
                                         └─[Back]→ 기분 선택

블렌딩 중에는 향료마다
    1) 회전판 모터로 해당 향료 병 위치까지 회전
    2) LoRa 로 서브보드에 [ID][sensor_id][ml] 전송
    3) 서브보드가 "DONE" 을 보낼 때까지 대기 (1초 단위로 수신 재시도)

[mock 에서 추가한 부분]
dashboard/dataCollector.py 가 읽는 시리얼 프로토콜(STATUS / MOOD / PERFUME / WATER_X / WATER_O)을
출력한다. 현재 main.c 에는 이 printf 가 없어서, 실제 보드에서도 대시보드를 쓰려면
README 의 "펌웨어에 추가할 printf" 를 main.c 에 넣어야 한다.
"""
import queue
import threading

from . import protocol
from .hardware import VirtualStepperMotor

# --- main.c 의 상수들 -----------------------------------------------------------
SCREEN_START, SCREEN_MOOD_SELECT, SCREEN_CONFIRM, SCREEN_BLENDING, SCREEN_FINISH = range(5)

# 대시보드(views.py C_STATUS_MESSAGES)가 기대하는 상태 문자열
STATUS_NAMES = {
    SCREEN_START: "SCREEN_START",
    SCREEN_MOOD_SELECT: "SCREEN_MOODSELECT",
    SCREEN_CONFIRM: "SCREEN_CONFIRM",
    SCREEN_BLENDING: "SCREEN_BLENDING",
    SCREEN_FINISH: "SCREEN_FINISH",
}

TOUCH_KEY = [1 << i for i in range(8)]  # TOUCH_KEY0 ~ TOUCH_KEY7

# DecodeMoodFromTouch(): 어떤 터치 키가 어떤 기분인지
MOOD_TO_KEY = {1: 7, 2: 3, 3: 6, 4: 2, 5: 5, 6: 1, 7: 4, 8: 0}
KEY_START = TOUCH_KEY[0]  # 확인 화면 [Start]
KEY_BACK = TOUCH_KEY[4]   # 확인 화면 [Back]

# RunBlendingProcess() 의 레시피 (Lavender, Cedarwood, Vanilla, Bergamot) — 단위 ml
RECIPES = {
    1: (1, 1, 1, 4),   # Fresh
    2: (8, 4, 2, 2),   # Calm
    3: (2, 6, 2, 4),   # Bold (confident)
    4: (4, 2, 8, 2),   # Sweet & romantic
    5: (2, 2, 2, 10),  # Active (energetic)
    6: (4, 4, 8, 2),   # Cozy
    7: (1, 4, 1, 1),   # Deep & mystic
}

# 향료 병 각도 (Lavender_angle, Cedarwood_angle, Vanilla_angle, Bergamot_angle)
BOTTLE_ANGLES = {1: 0, 2: 90, 3: 180, 4: 270}

RX_TIMEOUT_VALUE = 1000  # ms


def mood_to_touch(mood: int) -> int:
    return TOUCH_KEY[MOOD_TO_KEY[mood]]


def decode_mood_from_touch(touch: int) -> int:
    for mood in (1, 2, 3, 4, 5, 6, 7, 8):  # main.c 와 같은 우선순위
        if touch & mood_to_touch(mood):
            return mood
    return 0


class MainBoard:
    def __init__(self, radio, clock, lcd, tanks, serial, packet_id=protocol.PACKET_ID):
        self.radio = radio
        self.clock = clock
        self.lcd = lcd
        self.tanks = tanks
        self.serial = serial
        self.packet_id = packet_id

        self.current_state = SCREEN_START
        self.needs_redraw = True
        self.selected_mood = 0
        self.last_touch_time = 0

        self.rotary = VirtualStepperMotor("rotary", clock)
        self.current_angle = 0

        self._rx = queue.Queue()
        radio.on_rx_done = self._rx.put  # OnRxDone 콜백
        self._water_low = {}  # 대시보드에 마지막으로 보고한 상태 (True = 부족)
        self._shortage = {}   # 레시피보다 적게 남아 제조를 못 한 향료 {id: 그때 잔량}

    # ------------------------------------------------------------------ util
    def printf(self, text: str):
        self.serial.printf(text)

    def start(self):
        threading.Thread(target=self.main, name="main-board", daemon=True).start()
        return self

    # ------------------------------------------------------------------ main()
    def main(self):
        self.printf("Combined UI & Motor Controller (Queue Ver)")
        self.clock.delay(2500)
        self.printf("System Ready.")
        self.printf("UI: Draw Screen 1")
        self.report_water_levels(force=True)

        while True:
            # 1. 화면 그리기 & 로직 실행
            if self.needs_redraw:
                self.needs_redraw = False
                state = self.current_state
                if state == SCREEN_START:
                    self.draw_screen_start()
                elif state == SCREEN_MOOD_SELECT:
                    self.draw_screen_mood_select()
                elif state == SCREEN_CONFIRM:
                    self.draw_screen_confirm(self.selected_mood)
                elif state == SCREEN_BLENDING:
                    self.draw_screen_blending()
                    self.run_blending_process(self.selected_mood)
                elif state == SCREEN_FINISH:
                    self.draw_screen_finish()

            # 2. 터치 감지 (블렌딩 중엔 무시)
            if self.current_state != SCREEN_BLENDING and self.lcd.touch_pending():
                if self.clock.tick() - self.last_touch_time > 200:
                    touch = self.lcd.read_touch()
                    if touch:
                        self.process_touch(touch)
                        self.last_touch_time = self.clock.tick()

            # 3. [mock 추가] 수위 센서 주기적 확인
            self.report_water_levels()
            self.clock.delay(10)

    # ------------------------------------------------------------------ 터치
    def process_touch(self, touch: int):
        self.printf(f"ProcessTouch: 0x{touch:02X} (state={self.current_state})")
        state = self.current_state

        if state == SCREEN_START:
            self.current_state, self.needs_redraw = SCREEN_MOOD_SELECT, True

        elif state == SCREEN_MOOD_SELECT:
            mood = decode_mood_from_touch(touch)
            if mood == 8:  # Random
                mood = (self.clock.tick() % 7) + 1
            if mood == 0:
                return
            self.selected_mood = mood
            self.printf(f"MOOD : {mood}")  # [대시보드용]
            self.current_state, self.needs_redraw = SCREEN_CONFIRM, True

        elif state == SCREEN_CONFIRM:
            if touch & KEY_BACK:
                self.current_state, self.needs_redraw = SCREEN_MOOD_SELECT, True
            elif touch & KEY_START:
                self.send_start_command(self.selected_mood)
                self.current_state, self.needs_redraw = SCREEN_BLENDING, True

        elif state == SCREEN_FINISH:
            self.current_state, self.selected_mood, self.needs_redraw = SCREEN_START, 0, True

        if self.needs_redraw:
            self.clock.delay(300)

    # ------------------------------------------------------------------ 블렌딩
    def run_blending_process(self, mood: int):
        self.printf(f">>> Blending Start: Mood {mood} <<<")
        recipe = RECIPES.get(mood)
        if recipe is None:
            self.printf(f"[Blending] Unknown mood: {mood}")
        elif self._check_stock(recipe):
            for sensor_id, ml in zip((1, 2, 3, 4), recipe):
                self.move_and_inject(sensor_id, ml)
            self.printf(">>> Blending Complete! <<<")
            self.reset_motor()
            self.current_state, self.needs_redraw = SCREEN_FINISH, True
            return

        # [mock 추가] 향료가 모자라면 제조하지 않고 기분 선택 화면으로 돌아감
        self.draw_screen_refill()
        self.clock.delay(2000)
        self.current_state, self.needs_redraw = SCREEN_MOOD_SELECT, True

    def _check_stock(self, recipe) -> bool:
        lacking = [sid for sid, ml in zip((1, 2, 3, 4), recipe) if not self.tanks.has(sid, ml)]
        for sid in lacking:
            self.printf(f"[Blending] {protocol.PERFUMES[sid]} 부족 — 제조 중단")
            self._shortage[sid] = self.tanks.levels[sid]  # 리필되기 전까지 '부족'으로 보고
        self.report_water_levels()
        return not lacking

    def move_and_inject(self, sensor_id: int, ml: float):
        """main.c 의 LavenderMove / CedarwoodMove / VanillaMove / BergamotMove 를 하나로 합친 것"""
        move_angle = BOTTLE_ANGLES[sensor_id] - self.current_angle
        if move_angle > 180:
            move_angle -= 360
        if move_angle < -180:
            move_angle += 360
        self.rotary.move_steps(int(1024 * move_angle / 90), 2)
        self.current_angle = (self.current_angle + move_angle + 360) % 360

        self.printf(f"PERFUME : {protocol.PERFUMES[sensor_id]} : {ml}")  # [대시보드용]
        packet = protocol.build_job_packet(self.packet_id, sensor_id, float(ml))
        self.printf(f"sensor_id: {sensor_id}, rotation_ml: {float(ml):.2f}")
        self._drain_rx()
        self.radio.send(packet)
        self.wait_for_lora_ok_blocking()
        self.report_water_levels()

    def wait_for_lora_ok_blocking(self):
        """main.c 의 WaitForLoRaOK_Blocking(): DONE 이 올 때까지 1초씩 수신을 반복"""
        self.printf(f"Waiting for OK (Rx_ID = {self.packet_id})...")
        retries = 0
        while True:
            try:
                packet = self._rx.get(timeout=RX_TIMEOUT_VALUE / 1000 / self.clock.speed)
            except queue.Empty:
                retries += 1
                if retries == 1 or retries % 10 == 0:  # 실제로는 1초마다 출력되지만 너무 많아서 줄임
                    self.printf(f"RX timeout or error. Retrying... ({retries})")
                continue
            if protocol.is_done_packet(packet, self.packet_id):
                self.printf("Received DONE message!")
                return
            if packet[0] != self.packet_id:
                self.printf(f"Received message with wrong Rx_ID: {packet[0]}")
            else:
                self.printf(f"Received message, but not DONE: {packet[1:]!r}")

    def send_start_command(self, mood: int):
        self.printf(f"LoRa: SEND START (mood={mood})")
        self.radio.send(protocol.build_start_packet(self.packet_id, mood))

    def reset_motor(self):
        self.printf("[Motor] Resetting to Home...")
        self.current_angle = 0  # main.c 에서도 리밋 스위치 루프는 주석 처리돼 있음
        self.printf("[Motor] Homed.")

    def _drain_rx(self):
        while not self._rx.empty():
            self._rx.get_nowait()

    # ------------------------------------------------------------------ [mock 추가] 수위 센서
    def report_water_levels(self, force: bool = False):
        """
        대시보드 규칙: WATER_X : n → n번 향료 부족 / WATER_O : 0 → 전체 충분.
        상태가 바뀔 때만 보낸다.
        """
        for sid, level in list(self._shortage.items()):
            if self.tanks.levels[sid] > level:  # 리필됨
                del self._shortage[sid]
        now = {sid: self.tanks.is_low(sid) or sid in self._shortage for sid in protocol.PERFUMES}
        if not force and now == self._water_low:
            return
        recovered = any(self._water_low.get(sid) and not low for sid, low in now.items())
        if force or recovered:
            self.printf("WATER_O : 0")
            for sid, low in now.items():
                if low:
                    self.printf(f"WATER_X : {sid}")
        else:
            for sid, low in now.items():
                if low and not self._water_low.get(sid):
                    self.printf(f"WATER_X : {sid}")
        self._water_low = now

    # ------------------------------------------------------------------ 화면 (main.c Draw_Screen_*)
    def _status(self):
        self.printf(f"STATUS : {STATUS_NAMES[self.current_state]}")  # [대시보드용]

    def draw_screen_start(self):
        self.lcd.clear()
        self.lcd.draw_string(25, 30, "DAILY MOOD")
        self.lcd.draw_string(13, 48, "PERFUME MAKER")
        self.lcd.draw_string(5, 104, "Tap to continue")
        self.lcd.flush("START")
        self._status()

    def draw_screen_mood_select(self):
        self.lcd.clear()
        for (x, y), name in zip(
            [(6, 6), (74, 6), (6, 40), (74, 40), (6, 74), (74, 74), (6, 108), (74, 108)],
            protocol.MOOD_NAMES[1:],
        ):
            self.lcd.draw_string(x, y, name)
        self.lcd.flush("MOOD SELECT")
        self._status()

    def draw_screen_confirm(self, mood: int):
        self.lcd.clear()
        self.lcd.draw_string(20, 40, f"Mood: {protocol.MOOD_NAMES[mood]}")
        self.lcd.draw_string(7, 106, "[Back]")
        self.lcd.draw_string(70, 106, "[Start]")
        self.lcd.flush("CONFIRM")
        self._status()

    def draw_screen_blending(self):
        self.lcd.clear()
        self.lcd.draw_string(20, 50, "Blending...")
        self.lcd.draw_string(20, 70, "Please wait!")
        self.lcd.flush("BLENDING")
        self._status()

    def draw_screen_finish(self):
        self.lcd.clear()
        self.lcd.draw_string(40, 15, "Finish!")
        self.lcd.draw_string(16, 40, "Your perfume")
        self.lcd.draw_string(15, 60, "is now ready.")
        self.lcd.draw_string(22, 104, "Tap to home")
        self.lcd.flush("FINISH")
        self._status()

    def draw_screen_refill(self):
        self.lcd.clear()
        self.lcd.draw_string(10, 40, "Not enough")
        self.lcd.draw_string(10, 60, "perfume! Refill.")
        self.lcd.flush("REFILL NEEDED")
