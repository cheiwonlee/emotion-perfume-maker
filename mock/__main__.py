"""
대시보드 없이 가상 보드만 단독으로 실행:

    python -m mock            # 직접 조작
    python -m mock --auto     # 자동 시연

메인보드가 시리얼로 내보내는 줄([UART] ...)과 서브보드 로그([SUB] ...)가 모두 출력된다.
"""
import argparse

from .console import interactive
from .system import create_virtual_system


def add_mock_arguments(parser):
    g = parser.add_argument_group("mock 옵션")
    g.add_argument("--speed", type=float, default=5.0, help="시뮬레이션 배속 (기본 5배, 1 = 실제 속도)")
    g.add_argument("--loss", type=float, default=0.0, help="LoRa 패킷 유실 확률 0~1 (기본 0)")
    g.add_argument("--sub-id", type=int, default=121, help="서브보드 LoRa ID (기본 121, 예전 코드의 ID 불일치를 재현하려면 20)")
    g.add_argument("--capacity", type=float, default=30.0, help="향료 통 하나의 용량 ml (기본 30)")
    g.add_argument("--auto", action="store_true", help="자동 시연 모드로 시작")


def main():
    parser = argparse.ArgumentParser(prog="python -m mock", description="Daily Mood Perfume Maker 가상 하드웨어")
    add_mock_arguments(parser)
    parser.add_argument("--quiet", action="store_true", help="시리얼/서브보드 로그 숨기기")
    args = parser.parse_args()

    system = create_virtual_system(
        speed=args.speed, loss_rate=args.loss, sub_id=args.sub_id, capacity_ml=args.capacity,
        show_serial=not args.quiet, show_sub_log=not args.quiet,
    )
    interactive(system, auto=args.auto)


if __name__ == "__main__":
    main()
