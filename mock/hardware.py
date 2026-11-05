"""
가상 부품들: 스테핑 모터, 향료 통(수위 센서), 터치 LCD.

모든 시간은 VirtualClock 을 거치므로 --speed 값으로 시뮬레이션 속도를 바꿀 수 있다.
(speed=1 이면 실제 보드와 같은 시간, speed=10 이면 10배 빠르게)
"""
import queue
import threading
import time


class VirtualClock:
    def __init__(self, speed: float = 1.0):
        self.speed = max(speed, 0.01)
        self._start = time.monotonic()

    def delay(self, ms: float):
        """HAL_Delay(ms) 대응"""
        time.sleep(ms / 1000 / self.speed)

    def tick(self) -> int:
        """HAL_GetTick() 대응 (보드 기준 경과 ms)"""
        return int((time.monotonic() - self._start) * 1000 * self.speed)


class VirtualStepperMotor:
    """28BYJ-48 + ULN2003 같은 4선 스테핑 모터. half-step 8단계, 1회전 = 4096 스텝."""

    ONE_CYCLE = 4096

    def __init__(self, name: str, clock: VirtualClock):
        self.name = name
        self.clock = clock
        self.position = 0  # 누적 스텝 수

    def move_steps(self, steps: int, delay_ms: float):
        # 실제로는 스텝마다 코일 4개를 켜고 끄지만, mock 에서는 걸리는 시간만 흉내 낸다.
        self.clock.delay(abs(steps) * delay_ms)
        self.position += steps

    @property
    def angle(self) -> float:
        return (self.position % self.ONE_CYCLE) * 360 / self.ONE_CYCLE


class VirtualPerfumeTanks:
    """
    향료 통 4개와 비접촉 수위 센서.
    잔량이 low_level_ml 아래로 떨어지면 센서가 '부족'을 감지한다.
    """

    def __init__(self, capacity_ml: float = 30.0, low_level_ml: float = 5.0):
        self.capacity_ml = capacity_ml
        self.low_level_ml = low_level_ml
        self._lock = threading.Lock()
        self.levels = {sid: capacity_ml for sid in (1, 2, 3, 4)}

    def take(self, sensor_id: int, ml: float):
        with self._lock:
            self.levels[sensor_id] = max(0.0, self.levels.get(sensor_id, 0.0) - ml)

    def has(self, sensor_id: int, ml: float) -> bool:
        return self.levels.get(sensor_id, 0.0) >= ml

    def is_low(self, sensor_id: int) -> bool:
        """수위 센서 값. True = 액체가 감지되지 않음(부족)"""
        return self.levels.get(sensor_id, 0.0) < self.low_level_ml

    def refill(self, sensor_id: int | None = None):
        with self._lock:
            for sid in ([sensor_id] if sensor_id else list(self.levels)):
                self.levels[sid] = self.capacity_ml

    def drain(self, sensor_id: int):
        with self._lock:
            self.levels[sensor_id] = 0.0


class VirtualTouchLCD:
    """
    UART3 로 연결된 터치 LCD.
    - draw_string/clear : 화면에 글자 그리기 (화면이 바뀌면 on_screen 콜백 호출)
    - press(mask)       : 사람이 터치한 것처럼 터치 키 비트마스크를 넣는다
    - read_touch()      : 펌웨어가 LCD_SendTouchRequest() 로 읽는 값
    """

    def __init__(self, on_screen=None):
        self.on_screen = on_screen
        self._buffer = []
        self._touches = queue.Queue()

    # --- 펌웨어 쪽 -----------------------------------------------------------
    def clear(self):
        self._buffer = []

    def draw_string(self, x: int, y: int, text: str):
        self._buffer.append((y, x, text[:16]))  # 실제 LCD 도 16글자까지만 그림

    def flush(self, title: str):
        if self.on_screen:
            self.on_screen(title, sorted(self._buffer))

    def touch_pending(self) -> bool:
        """PB7 터치 인터럽트 핀이 LOW 인지"""
        return not self._touches.empty()

    def read_touch(self) -> int:
        try:
            return self._touches.get_nowait()
        except queue.Empty:
            return 0

    # --- 사람(콘솔) 쪽 --------------------------------------------------------
    def press(self, mask: int):
        self._touches.put(mask)
