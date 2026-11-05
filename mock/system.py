"""
가상 하드웨어 전체를 한 번에 조립한다.

    [터치 LCD] ── 메인보드 ──(LoRa)── 서브보드 ── [주사기 모터 ×4]
                    │                              │
               [회전판 모터]                   [향료 통 ×4 / 수위 센서]
                    │
            가상 시리얼(UART2) ──→ dashboard/dataCollector.py
"""
from dataclasses import dataclass

from . import protocol
from .hardware import VirtualClock, VirtualPerfumeTanks, VirtualTouchLCD
from .lora import VirtualLoRaChannel, VirtualRadio
from .main_board import MainBoard
from .serial_port import MockSerial
from .sub_board import SubBoard


def render_lcd(title, cells, out=print):
    """LCD 화면을 터미널에 박스로 그린다. cells = [(y, x, text), ...]"""
    width = 34
    out("┌─ LCD: " + title + " " + "─" * max(0, width - len(title) - 8) + "┐")
    rows = {}
    for y, x, text in cells:
        rows.setdefault(y, []).append((x, text))
    for y in sorted(rows):
        line = ""
        for x, text in sorted(rows[y]):
            col = x // 6  # 글자 하나 ≈ 6px
            line = line.ljust(col) + text
        out("│ " + line[: width - 1].ljust(width - 1) + "│")
    out("└" + "─" * width + "┘")


@dataclass
class VirtualSystem:
    clock: VirtualClock
    serial: MockSerial
    lcd: VirtualTouchLCD
    tanks: VirtualPerfumeTanks
    channel: VirtualLoRaChannel
    main_board: MainBoard
    sub_board: SubBoard


def create_virtual_system(
    speed: float = 5.0,
    loss_rate: float = 0.0,
    sub_id: int = protocol.PACKET_ID,
    capacity_ml: float = 30.0,
    show_lcd: bool = True,
    show_serial: bool = False,
    show_sub_log: bool = False,
    out=print,
) -> VirtualSystem:
    clock = VirtualClock(speed)
    serial = MockSerial(echo=(lambda line: out(f"  [UART] {line}")) if show_serial else None)
    lcd = VirtualTouchLCD(on_screen=(lambda t, c: render_lcd(t, c, out)) if show_lcd else None)
    tanks = VirtualPerfumeTanks(capacity_ml=capacity_ml)
    channel = VirtualLoRaChannel(airtime_ms=30 / clock.speed, loss_rate=loss_rate, log=out)  # 전파 시간도 배속에 맞춤

    main_radio = VirtualRadio("main-board", channel)
    sub_radio = VirtualRadio("sub-board", channel)

    sub = SubBoard(sub_radio, clock, tanks, rx_id=sub_id,
                   log=(lambda m: out(f"  [SUB] {m}")) if show_sub_log else None)
    main = MainBoard(main_radio, clock, lcd, tanks, serial)

    sub.start()
    main.start()
    return VirtualSystem(clock, serial, lcd, tanks, channel, main, sub)
