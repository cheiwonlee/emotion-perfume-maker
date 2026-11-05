"""
가상 시리얼 포트 (UART2, 115200).

메인보드의 printf() 출력이 여기에 한 줄씩 쌓이고,
dashboard/dataCollector.py 는 pyserial 의 serial.Serial 을 쓰듯이 readline() 으로 읽는다.
"""
import queue


class MockSerial:
    def __init__(self, port: str = "MOCK", timeout: float = 1.0, echo=None):
        self.port = port
        self.timeout = timeout
        self.is_open = True
        self._lines = queue.Queue()
        self._echo = echo  # 보드가 출력한 줄을 화면에도 보여주고 싶을 때 쓰는 콜백

    # --- 보드(펌웨어) 쪽에서 사용 -------------------------------------------
    def printf(self, text: str):
        for line in text.splitlines():
            self._lines.put(line)
            if self._echo:
                self._echo(line)

    # --- PC(dataCollector) 쪽에서 사용: pyserial 과 같은 인터페이스 ----------------
    def readline(self) -> bytes:
        try:
            line = self._lines.get(timeout=self.timeout)
        except queue.Empty:
            return b""  # pyserial 도 timeout 이 지나면 빈 bytes 를 돌려줌
        return (line + "\n").encode("utf-8")

    def close(self):
        self.is_open = False
