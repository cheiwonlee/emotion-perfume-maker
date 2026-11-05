"""
Daily Mood Perfume Maker 가상 하드웨어(mock).

실제 STM32 보드, LoRa 모듈, 스테핑 모터, 수위 센서, 터치 LCD 없이도
main-board / sub-board 펌웨어와 같은 순서로 동작하며,
dashboard 가 읽는 시리얼 출력을 그대로 만들어 낸다.
"""
from .system import create_virtual_system  # noqa: F401
