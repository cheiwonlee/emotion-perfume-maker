"""
지금 실행 중인 가상 시스템을 담아 두는 곳.

run.py 가 가상 보드를 만든 뒤 register() 하면, 같은 프로세스에서 돌고 있는 Django 가
dashboard/sensor/mock_bridge.py 를 통해 가상 LCD 를 누르거나 향료 통을 비울 수 있다.
실제 보드로 실행할 때는 아무것도 등록되지 않으므로 대시보드에 가상 LCD 가 나타나지 않는다.
"""
from . import protocol
from .main_board import KEY_BACK, KEY_START, STATUS_NAMES, mood_to_touch

system = None
demo = None


def register(virtual_system, auto_demo=None):
    global system, demo
    system, demo = virtual_system, auto_demo


def is_active() -> bool:
    return system is not None


def snapshot() -> dict:
    title, cells = system.lcd.screen
    tanks = system.tanks
    return {
        "screen": STATUS_NAMES[system.main_board.current_state],
        "lcd": {"title": title, "cells": [{"x": x, "y": y, "text": t} for y, x, t in cells]},
        "tanks": [
            {"id": sid, "name": name, "ml": round(tanks.levels[sid], 1),
             "capacity": tanks.capacity_ml, "low_level": tanks.low_level_ml, "is_low": tanks.is_low(sid)}
            for sid, name in protocol.PERFUMES.items()
        ],
        "auto": bool(demo and demo.running),
        "speed": system.clock.speed,
    }


def press(key: str, mood: int | None = None):
    masks = {"tap": 0x01, "start": KEY_START, "back": KEY_BACK}
    if key == "mood":
        if mood not in range(1, 9):
            raise ValueError("mood 는 1~8")
        system.lcd.press(mood_to_touch(mood))
    elif key in masks:
        system.lcd.press(masks[key])
    else:
        raise ValueError(f"알 수 없는 키: {key}")


def tank(action: str, sensor_id: int | None = None):
    if action == "drain" and sensor_id in protocol.PERFUMES:
        system.tanks.drain(sensor_id)
    elif action == "refill":
        system.tanks.refill(sensor_id)
    else:
        raise ValueError("action 은 drain(id 필요) 또는 refill")


def set_auto(on: bool):
    if demo and demo.running != on:
        demo.toggle()
