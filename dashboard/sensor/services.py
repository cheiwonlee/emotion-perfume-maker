"""
보드에서 들어온 이벤트를 DB 에 반영하는 로직.
views.py 는 요청을 받고 응답하는 일만 하고, 실제 처리는 여기서 한다. (테스트하기도 쉬워짐)
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import constants as C
from .models import Blend, DeviceStatus, Injection, StockEvent


def _open_blend():
    return Blend.objects.filter(finished_at__isnull=True).first()


@transaction.atomic
def heartbeat(serial_connected: bool):
    status = DeviceStatus.current()
    status.serial_connected = serial_connected
    status.last_seen = timezone.now()
    status.save(update_fields=["serial_connected", "last_seen"])


@transaction.atomic
def update_screen(screen: str, serial_connected: bool = True):
    status = DeviceStatus.current()
    previous = status.screen
    status.screen = screen
    status.serial_connected = serial_connected
    status.last_seen = timezone.now()
    status.save()

    if screen == previous:
        return
    blend = _open_blend()
    if screen == C.SCREEN_BLENDING:
        if blend:  # 이전 제조가 끝나지 않은 채 새로 시작 → 이전 것은 중단 처리
            blend.finished_at = timezone.now()
            blend.save()
        Blend.objects.create(mood_code=status.mood_code)
    elif blend:
        blend.finished_at = timezone.now()
        blend.completed = screen == C.SCREEN_FINISH
        blend.save()


def set_mood(code: int):
    if code not in C.MOODS:
        raise ValueError(f"알 수 없는 기분 코드: {code}")
    DeviceStatus.objects.filter(pk=DeviceStatus.current().pk).update(mood_code=code)


def record_injection(perfume: str, ml: float):
    if perfume not in C.PERFUME_IDS:
        raise ValueError(f"알 수 없는 향료: {perfume}")
    return Injection.objects.create(blend=_open_blend(), perfume=perfume, ml=ml)


def latest_stock(perfume: str):
    event = StockEvent.objects.filter(perfume=perfume).first()
    return event.is_low if event else None


@transaction.atomic
def record_water(sensor_id: int):
    """sensor_id 0 → 모든 향료 충분, 1~4 → 해당 향료 부족. 값이 바뀐 경우에만 기록한다."""
    if sensor_id == 0:
        changes = {name: False for name in C.PERFUMES.values()}
    elif sensor_id in C.PERFUMES:
        changes = {C.PERFUMES[sensor_id]: True}
    else:
        raise ValueError(f"알 수 없는 센서 번호: {sensor_id}")
    for name, is_low in changes.items():
        if latest_stock(name) != is_low:
            StockEvent.objects.create(perfume=name, is_low=is_low)


# --------------------------------------------------------------------------- 조회
def _iso(dt):
    return dt.isoformat() if dt else None


def _blend_json(blend: Blend):
    injected = {}
    for inj in blend.injections.all():
        injected[inj.perfume] = injected.get(inj.perfume, 0) + inj.ml
    recipe = C.RECIPES.get(blend.mood_code, {})
    steps = [
        {"perfume": name, "planned_ml": recipe.get(name), "injected_ml": injected.get(name)}
        for name in C.PERFUMES.values()
    ]
    name, label = C.MOODS.get(blend.mood_code, (None, None))
    return {
        "id": blend.id,
        "mood": name,
        "mood_label": label,
        "started_at": _iso(blend.started_at),
        "finished_at": _iso(blend.finished_at),
        "completed": blend.completed,
        "active": blend.finished_at is None,
        "total_ml": sum(injected.values()),
        "steps": steps,
    }


def dashboard_state():
    status = DeviceStatus.current()
    now = timezone.now()
    online = bool(
        status.serial_connected
        and status.last_seen
        and now - status.last_seen < timedelta(seconds=settings.DEVICE_OFFLINE_AFTER_SECONDS)
    )

    stock = []
    for sid, name in C.PERFUMES.items():
        events = list(StockEvent.objects.filter(perfume=name)[:24])
        stock.append({
            "id": sid,
            "name": name,
            "is_low": events[0].is_low if events else None,  # None = 아직 센서 값 없음
            "since": _iso(events[0].created_at) if events else None,
            "history": [{"t": _iso(e.created_at), "is_low": e.is_low} for e in reversed(events)],
        })

    blends = list(Blend.objects.prefetch_related("injections")[:8])
    today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    mood_name, mood_label = C.MOODS.get(status.mood_code, (None, None))

    return {
        "device": {
            "online": online,
            "screen": status.screen,
            "screen_text": C.SCREEN_TEXT.get(status.screen, "보드 신호를 기다리는 중"),
            "last_seen": _iso(status.last_seen),
        },
        "mood": {
            "code": status.mood_code, "name": mood_name, "label": mood_label,
            "recipe": C.RECIPES.get(status.mood_code),
        } if status.mood_code else None,
        "current_blend": _blend_json(blends[0]) if blends else None,
        "recent_blends": [_blend_json(b) for b in blends if b.finished_at][:6],
        "today_count": Blend.objects.filter(completed=True, started_at__gte=today).count(),
        "stock": stock,
    }
