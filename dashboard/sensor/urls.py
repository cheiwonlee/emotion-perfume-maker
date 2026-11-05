from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/state", views.api_state, name="api_state"),

    # 수집기(dataCollector.py)가 보드 이벤트를 보내는 곳 — 이름은 기존과 동일하게 유지
    path("setDeviceStatus", views.set_device_status, name="setDeviceStatus"),
    path("setMood", views.set_mood, name="setMood"),
    path("setPerfume", views.set_perfume, name="setPerfume"),
    path("setWaterStatus", views.set_water_status, name="setWaterStatus"),

    # 가상 보드 조작 (python run.py 로 실행했을 때만 동작)
    path("api/mock/press", views.mock_press, name="mock_press"),
    path("api/mock/tank", views.mock_tank, name="mock_tank"),
    path("api/mock/auto", views.mock_auto, name="mock_auto"),
]
