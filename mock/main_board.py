"""
메인보드(터치 LCD + 회전판 모터 + LoRa 마스터) mock — main-board/Core/Src/main.c 를 옮긴 것.

흐름 (main.c 와 동일)
    START 화면 ─터치→ 기분 선택 ─기분 터치→ 확인 ─[Start]→ 블렌딩 ─완료→ FINISH ─터치→ START
                                         └─[Back]→ 기분 선택

블렌딩 중에는 향료마다
    1) 회전판 모터로 해당 향료 병 위치까지 회전
    2) LoRa 로 서브보드에 [ID][sensor_id][ml] 전송
    3) 서브보드 응답 대기 — "DONE"(완료, 주입 후 수위 포함) / "LOW"(향료 부족) / 시간 초과

[대시보드용 출력] STATUS / MOOD / PERFUME / WATER_X / WATER_O 줄은 main.c 의 printf 와 같은 형식이다.
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
LEVEL_QUERY_INTERVAL_MS = 30000

REPLY_DONE, REPLY_LOW, REPLY_TIMEOUT = "DONE", "LOW", "TIMEOUT"  # main.c SyringeReply_t


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
        self.last_level_query = 0

        self.rotary = VirtualStepperMotor("rotary", clock)
        self.current_angle = 0

        self._rx = queue.Queue()
        radio.on_rx_done = self._rx.put  # OnRxDone 콜백

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

        while True:
            # 1. 화면 그리기 & 로직 실행
            if self.needs_redraw:
                self.needs_redraw = False
                state = self.current_state
                if state == SCREEN_START:
                    self.draw_screen_start()
                    self.query_levels()
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

            # 3. 시작 화면에서 기다리는 동안 주기적으로 수위 확인
            if (self.current_state == SCREEN_START and not self.needs_redraw
                    and self.clock.tick() - self.last_level_query > LEVEL_QUERY_INTERVAL_MS):
                self.query_levels()
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
            self.current_state, self.needs_redraw = SCREEN_MOOD_SELECT, True
            return

        for sensor_id, ml in zip((1, 2, 3, 4), recipe):
            reply = self.inject_perfume(sensor_id, ml)
            if reply != REPLY_DONE:
                # 향료 부족 / 서브보드 무응답 → 제조를 멈추고 기분 선택 화면으로
                name = protocol.PERFUMES[sensor_id]
                if reply == REPLY_LOW:
                    self.printf(f"[Blending] {name} is LOW - stopped")
                    self.draw_screen_message("Refill needed:", name)
                else:
                    self.printf("[Blending] No reply from syringe board - stopped")
                    self.draw_screen_message("No reply from", "syringe board")
                self.clock.delay(2500)
                self.reset_motor()
                self.current_state, self.needs_redraw = SCREEN_MOOD_SELECT, True
                return

        self.printf(">>> Blending Complete! <<<")
        self.reset_motor()
        self.current_state, self.needs_redraw = SCREEN_FINISH, True

    def inject_perfume(self, sensor_id: int, ml: float) -> str:
        """main.c InjectPerfume(): 회전판 이동 → 주입 요청 → 응답 대기 → 수위 출력"""
        move_angle = BOTTLE_ANGLES[sensor_id] - self.current_angle
        if move_angle > 180:
            move_angle -= 360
        if move_angle < -180:
            move_angle += 360
        self.rotary.move_steps(int(1024 * move_angle / 90), 2)
        self.current_angle = (self.current_angle + move_angle + 360) % 360

        self.printf(f"PERFUME : {protocol.PERFUMES[sensor_id]} : {int(ml)}")  # [대시보드]
        self.printf(f"sensor_id: {sensor_id}, rotation_ml: {int(ml)}")
        self._drain_rx()
        self.radio.send(protocol.build_job_packet(self.packet_id, sensor_id, float(ml)))

        timeout_ms = ml * VirtualStepperMotor.ONE_CYCLE * 2 + 10000
        reply, level = self.wait_for_syringe_reply(timeout_ms)

        if reply == REPLY_LOW or (reply == REPLY_DONE and level == protocol.LEVEL_LOW):
            self.printf(f"WATER_X : {sensor_id}")  # [대시보드]
        elif reply == REPLY_DONE and level == protocol.LEVEL_OK:
            self.printf(f"WATER_O : {sensor_id}")  # [대시보드]
        return reply

    def wait_for_syringe_reply(self, timeout_ms: float):
        """main.c WaitForSyringeReply(): DONE / LOW 가 오거나 시간이 다 될 때까지 1초씩 수신 반복"""
        self.printf(f"Waiting for reply (Rx_ID = {self.packet_id})...")
        start = self.clock.tick()
        while self.clock.tick() - start < timeout_ms:
            try:
                packet = self._rx.get(timeout=RX_TIMEOUT_VALUE / 1000 / self.clock.speed)
            except queue.Empty:
                continue
            if packet[0] != self.packet_id:
                self.printf(f"Received message with wrong Rx_ID: {packet[0]}")
            elif protocol.is_done_packet(packet, self.packet_id):
                self.printf("Received DONE message!")
                return REPLY_DONE, packet[5] if len(packet) >= 6 else protocol.LEVEL_UNKNOWN
            elif protocol.is_low_packet(packet, self.packet_id):
                self.printf(f"Received LOW message (sensor {packet[4]})")
                return REPLY_LOW, protocol.LEVEL_LOW
            else:
                self.printf("Received message, but not DONE/LOW")
        self.printf(f"No reply within {int(timeout_ms)} ms")
        return REPLY_TIMEOUT, protocol.LEVEL_UNKNOWN

    def query_levels(self):
        """main.c QueryLevels(): 서브보드에 네 통의 수위를 묻고 WATER_X/O 출력"""
        self.last_level_query = self.clock.tick()
        self._drain_rx()
        self.radio.send(protocol.build_level_query(self.packet_id))
        start = self.clock.tick()
        while self.clock.tick() - start < 2000:
            try:
                packet = self._rx.get(timeout=RX_TIMEOUT_VALUE / 1000 / self.clock.speed)
            except queue.Empty:
                continue
            if protocol.is_level_reply(packet, self.packet_id):
                for sid, level in zip((1, 2, 3, 4), packet[4:8]):
                    if level == protocol.LEVEL_LOW:
                        self.printf(f"WATER_X : {sid}")  # [대시보드]
                    elif level == protocol.LEVEL_OK:
                        self.printf(f"WATER_O : {sid}")  # [대시보드]
                return
        self.printf("No level reply from syringe board")

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

    def draw_screen_message(self, line1: str, line2: str):
        """main.c Draw_Screen_Message()"""
        self.lcd.clear()
        self.lcd.draw_string(10, 40, line1)
        self.lcd.draw_string(10, 60, line2)
        self.lcd.flush("MESSAGE")
