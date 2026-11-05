#!/usr/bin/env python3
"""
명령 하나로 전체 시스템 실행.

    python run.py                 부품 없이 가상 보드로 실행 (브라우저가 자동으로 열림)
    python run.py --auto          가상 보드 + 자동 시연
    python run.py --real          실제 보드를 USB 로 연결해서 실행 (--serial COM3 로 포트 지정 가능)

하는 일: DB 준비(migrate) → 웹 서버 → (가상 보드) → 수집기 → 브라우저 열기
종료는 Ctrl+C.
"""
import argparse
import logging
import os
import socket
import sys
import threading
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [ROOT, os.path.join(ROOT, "dashboard")]


def parse_args():
    p = argparse.ArgumentParser(description="Daily Mood Perfume Maker 실행기")
    p.add_argument("--real", action="store_true", help="가상 보드 대신 실제 보드(시리얼) 사용")
    p.add_argument("--serial", help="--real 일 때 시리얼 포트 (예: COM3, /dev/ttyACM0)")
    p.add_argument("--port", type=int, default=8000, help="웹 서버 포트 (기본 8000)")
    p.add_argument("--no-browser", action="store_true", help="브라우저를 자동으로 열지 않기")
    g = p.add_argument_group("가상 보드 옵션")
    g.add_argument("--auto", action="store_true", help="자동 시연을 켠 채로 시작")
    g.add_argument("--speed", type=float, default=5.0, help="시뮬레이션 배속 (기본 5, 1 = 실제 속도)")
    g.add_argument("--loss", type=float, default=0.0, help="LoRa 패킷 유실 확률 0~1")
    g.add_argument("--sub-id", type=int, default=121, help="서브보드 LoRa ID (기본 121, 예전 코드의 ID 불일치를 재현하려면 20)")
    g.add_argument("--capacity", type=float, default=30.0, help="향료 통 용량 ml")
    return p.parse_args()


def port_in_use(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_web_server(port):
    """manage.py migrate + runserver 를 이 프로세스 안에서 실행한다."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "iotProject.settings")
    try:
        import django
    except ImportError:
        sys.exit("Django 가 설치돼 있지 않아요. 먼저 실행하세요:  pip install -r requirements.txt")
    django.setup()

    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.management import call_command
    from django.core.servers.basehttp import run as serve
    from django.core.wsgi import get_wsgi_application

    call_command("migrate", verbosity=0)
    app = StaticFilesHandler(get_wsgi_application())
    logging.getLogger("django.server").setLevel(logging.WARNING)  # 1초마다 찍히는 요청 로그 숨김
    threading.Thread(target=serve, args=("127.0.0.1", port, app), kwargs={"threading": True}, daemon=True).start()
    for _ in range(50):
        if port_in_use(port):
            return
        time.sleep(0.1)
    sys.exit("웹 서버를 시작하지 못했어요.")


def main():
    args = parse_args()
    if port_in_use(args.port):
        sys.exit(f"{args.port}번 포트를 이미 쓰고 있어요. 다른 실행을 끄거나 --port 8001 처럼 바꿔 주세요.")

    start_web_server(args.port)
    url = f"http://127.0.0.1:{args.port}/sensor/"

    from dataCollector import Collector, open_serial

    if args.real:
        ser = open_serial(args.serial)
        if ser is None:
            print("! 연결할 시리얼 포트가 없어요. 보드 USB 연결을 확인하세요. (대시보드는 '연결 끊김'으로 표시됩니다)")
        mode = "실제 보드"
    else:
        from mock import create_virtual_system, runtime
        from mock.console import AutoDemo

        system = create_virtual_system(
            speed=args.speed, loss_rate=args.loss, sub_id=args.sub_id,
            capacity_ml=args.capacity, show_lcd=False,
        )
        demo = AutoDemo(system)
        runtime.register(system, demo)
        if args.auto:
            demo.toggle()
        ser = system.serial
        mode = f"가상 보드 ({args.speed:g}배속)"

    Collector(ser, f"http://127.0.0.1:{args.port}").start()

    print(f"\n  Daily Mood Perfume Maker — {mode}\n  대시보드: {url}\n  종료: Ctrl+C\n")
    if not args.no_browser:
        webbrowser.open(url)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
