"""
대시보드 화면과 API.

보드(수집기) → 서버 : setDeviceStatus / setMood / setPerfume / setWaterStatus  (form POST)
브라우저 → 서버      : GET  api/state      화면에 필요한 모든 상태를 JSON 으로
                       POST api/mock/...   (가상 보드로 실행했을 때만) 가상 LCD·향료 통 조작
"""
import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from . import mock_bridge, services


def _ok(**data):
    return JsonResponse({"ok": True, **data})


def _bad(message, status=400):
    return JsonResponse({"ok": False, "message": message}, status=status)


def _int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"숫자가 아님: {value!r}")


# ----------------------------------------------------------------- 화면
@require_GET
@ensure_csrf_cookie  # 화면의 가상 LCD 버튼이 POST 할 때 쓸 CSRF 쿠키
def index(request):
    return render(request, "sensor/dashboard.html")


@require_GET
def api_state(request):
    state = services.dashboard_state()
    if mock_bridge.active():
        state["mock"] = mock_bridge.runtime.snapshot()
    return JsonResponse(state)


# ----------------------------------------------------------------- 보드(수집기)용
# 수집기는 브라우저가 아니라 CSRF 토큰이 없으므로 이 네 개만 예외로 둔다.
@csrf_exempt
@require_POST
def set_device_status(request):
    connected = request.POST.get("is_connected", "false").lower() == "true"
    screen = request.POST.get("c_status", "").strip()
    if screen:
        services.update_screen(screen, connected)
    else:  # 화면 정보 없이 오면 '살아 있다'는 신호(heartbeat)
        services.heartbeat(connected)
    return _ok()


@csrf_exempt
@require_POST
def set_mood(request):
    try:
        services.set_mood(_int(request.POST.get("mood_code")))
    except ValueError as e:
        return _bad(str(e))
    return _ok()


@csrf_exempt
@require_POST
def set_perfume(request):
    try:
        services.record_injection(request.POST.get("name", "").strip(), float(request.POST.get("value", "")))
    except ValueError as e:
        return _bad(str(e))
    return _ok()


@csrf_exempt
@require_POST
def set_water_status(request):
    try:
        services.record_water(_int(request.POST.get("sensor_id")))
    except ValueError as e:
        return _bad(str(e))
    return _ok()


# ----------------------------------------------------------------- 가상 보드 조작 (mock 전용)
def _mock_only(view):
    def wrapper(request):
        if not mock_bridge.active():
            return _bad("가상 보드로 실행 중이 아닙니다. `python run.py` 로 실행하세요.", status=404)
        try:
            body = json.loads(request.body or "{}")
            view(body)
        except (ValueError, json.JSONDecodeError) as e:
            return _bad(str(e))
        return _ok(mock=mock_bridge.runtime.snapshot())
    wrapper.__name__ = view.__name__
    return require_POST(wrapper)


@_mock_only
def mock_press(body):
    mock_bridge.runtime.press(body.get("key"), body.get("mood"))


@_mock_only
def mock_tank(body):
    mock_bridge.runtime.tank(body.get("action"), body.get("id"))


@_mock_only
def mock_auto(body):
    mock_bridge.runtime.set_auto(bool(body.get("on")))
