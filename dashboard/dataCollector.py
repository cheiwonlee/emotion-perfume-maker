"""
STM32 메인보드의 시리얼 출력을 읽어 Django 대시보드로 보내는 수집기.

    보드 printf  ──UART(USB)──►  parse_line()  ──큐──►  HTTP POST  ──►  Django

보드가 보내는 줄 형식
    STATUS : SCREEN_BLENDING      화면 상태
    MOOD : 2                      선택한 기분 번호
    PERFUME : Lavender : 4        주입한 향료와 양(ml)
    WATER_X : 3                   3번 향료 부족
    WATER_O : 0                   모든 향료 충분
그 밖의 줄(디버그 printf)은 무시한다.

실행
    python dataCollector.py                    # 실제 보드 (포트 자동 탐색)
    python dataCollector.py --port COM3        # 포트 직접 지정
    부품 없이 실행하려면 레포 루트에서  python run.py
"""
import argparse
import queue
import threading
import time
from dataclasses import dataclass

import requests

DEFAULT_SERVER = "http://127.0.0.1:8000"
HEARTBEAT_SECONDS = 1.0


# --------------------------------------------------------------------------- 파싱
@dataclass(frozen=True)
class Event:
    kind: str      # status / mood / perfume / water
    endpoint: str  # Django URL (sensor/ 뒤)
    data: dict     # POST 로 보낼 값


def parse_line(line: str) -> Event | None:
    """보드가 보낸 한 줄을 Event 로 바꾼다. 관심 없는 줄이면 None."""
    parts = [p.strip() for p in line.strip().split(":")]
    if len(parts) < 2 or not parts[1]:
        return None
    key = parts[0].upper()

    if key == "STATUS":
        return Event("status", "setDeviceStatus", {"c_status": parts[1], "is_connected": "true"})
    if key == "MOOD" and parts[1].isdigit():
        return Event("mood", "setMood", {"mood_code": parts[1]})
    if key == "PERFUME" and len(parts) >= 3:
        return Event("perfume", "setPerfume", {"name": parts[1], "value": parts[2]})
    if key == "WATER_X" and parts[1].isdigit():
        return Event("water", "setWaterStatus", {"sensor_id": parts[1]})
    if key == "WATER_O":
        return Event("water", "setWaterStatus", {"sensor_id": "0"})  # 0 = 전체 충분
    return None


# --------------------------------------------------------------------------- 수집기
class Collector:
    """
    스레드 3개로 동작한다.
      reader    : 시리얼에서 한 줄씩 읽어 이벤트 큐에 넣는다
      sender    : 큐에서 꺼내 순서대로 서버에 보낸다 (순서가 바뀌면 '어느 제조의 주입인지'가 틀어지므로)
      heartbeat : 1초마다 '연결돼 있음' 신호를 보낸다 (끊기면 대시보드가 오프라인으로 표시)
    """

    def __init__(self, ser, server: str = DEFAULT_SERVER, log=print):
        self.ser = ser
        self.server = server.rstrip("/")
        self.log = log
        self.connected = ser is not None
        self.events: "queue.Queue[Event]" = queue.Queue(maxsize=200)
        self.http = requests.Session()
        self._server_down = False

    def post(self, endpoint: str, data: dict):
        try:
            r = self.http.post(f"{self.server}/sensor/{endpoint}", data=data, timeout=2)
            r.raise_for_status()
            if self._server_down:
                self.log("[수집기] 서버 연결 복구")
            self._server_down = False
            return True
        except requests.RequestException as e:
            if not self._server_down:  # 같은 오류를 1초마다 찍지 않도록 한 번만
                self.log(f"[수집기] 서버로 보내지 못함: {e}")
            self._server_down = True
            return False

    def handle_line(self, line: str):
        event = parse_line(line)
        if event is None:
            return
        try:
            self.events.put_nowait(event)
        except queue.Full:
            self.log("[수집기] 이벤트가 너무 많이 밀려 하나를 버렸어요")

    # --- threads -----------------------------------------------------------
    def _reader(self):
        try:
            from serial import SerialException
            errors = (SerialException, OSError)
        except ImportError:  # 가상 시리얼만 쓸 때는 pyserial 이 없어도 된다
            errors = (OSError,)

        while self.connected:
            try:
                raw = self.ser.readline()
            except errors as e:
                self.log(f"[수집기] 시리얼 연결이 끊겼어요: {e}")
                self.connected = False
                break
            if raw:
                self.handle_line(raw.decode("utf-8", errors="replace"))

    def _sender(self):
        while True:
            event = self.events.get()
            if self.post(event.endpoint, event.data):
                self.log(f"[수집기] {event.kind:<7} {event.data}")

    def _heartbeat(self):
        while True:
            self.post("setDeviceStatus", {"is_connected": str(self.connected).lower()})
            time.sleep(HEARTBEAT_SECONDS)

    def start(self):
        for target in (self._sender, self._heartbeat):
            threading.Thread(target=target, daemon=True).start()
        if self.ser is not None:
            threading.Thread(target=self._reader, daemon=True).start()
        return self


# --------------------------------------------------------------------------- 실제 시리얼 포트
def open_serial(port: str | None = None, baud: int = 115200):
    """포트를 지정하지 않으면 STM32(ST-Link) 처럼 보이는 포트를 먼저 시도한다."""
    import serial
    import serial.tools.list_ports

    if port:
        return serial.Serial(port, baud, timeout=1)

    # hwid 가 'n/a' 인 포트는 메인보드에 붙은 옛 시리얼(예: /dev/ttyS0)이라 보드가 아니다 → USB 장치만 본다
    ports = [p for p in serial.tools.list_ports.comports() if p.hwid and p.hwid != "n/a"]
    ports.sort(key=lambda p: 0 if any(k in f"{p.description} {p.hwid}".upper() for k in ("STM", "ST-LINK", "STLINK", "0483")) else 1)
    for p in ports:
        try:
            ser = serial.Serial(p.device, baud, timeout=1)
            print(f"[수집기] {p.device} ({p.description}) 에 연결했어요")
            return ser
        except serial.SerialException:
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description="STM32 시리얼 → Django 대시보드 수집기")
    parser.add_argument("--port", help="시리얼 포트 (예: COM3, /dev/ttyACM0). 생략하면 자동 탐색")
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"Django 서버 주소 (기본 {DEFAULT_SERVER})")
    args = parser.parse_args()

    ser = open_serial(args.port)
    if ser is None:
        print("[수집기] 연결할 시리얼 포트가 없어요. 보드 USB 연결을 확인하거나, 부품 없이 보려면 레포 루트에서 `python run.py`")
    Collector(ser, args.server).start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
