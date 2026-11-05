from django.db import models
from django.utils import timezone

from .constants import MOODS


class DeviceStatus(models.Model):
    """
    기기의 현재 상태 (레코드는 항상 1개).
    예전에는 기분/주입 정보를 views.py 의 전역 변수에 담아 서버를 재시작하면 사라졌는데,
    이제 모두 DB 에 저장한다.
    """

    screen = models.CharField("보드 화면 상태", max_length=32, blank=True, default="")
    serial_connected = models.BooleanField("시리얼 연결", default=False)
    mood_code = models.PositiveSmallIntegerField("선택된 기분", null=True, blank=True)
    last_seen = models.DateTimeField("마지막 신호", null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "기기 상태"

    @classmethod
    def current(cls) -> "DeviceStatus":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Blend(models.Model):
    """향수 한 병을 만드는 한 번의 제조 (BLENDING 화면 진입 ~ FINISH)"""

    mood_code = models.PositiveSmallIntegerField(null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)  # False + finished_at 있음 = 중단됨

    class Meta:
        ordering = ["-started_at"]

    @property
    def mood_name(self):
        return MOODS.get(self.mood_code, ("?", ""))[0]

    def __str__(self):
        return f"{self.mood_name} @ {self.started_at:%H:%M:%S}"


class Injection(models.Model):
    """향료 한 종류를 주사기로 주입한 기록"""

    blend = models.ForeignKey(Blend, null=True, blank=True, on_delete=models.CASCADE, related_name="injections")
    perfume = models.CharField(max_length=20)
    ml = models.FloatField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]


class StockEvent(models.Model):
    """
    수위 센서 값이 바뀐 기록 (is_low=True → 부족).
    예전 ProximitySensor 테이블과 같은 역할이지만, 값이 바뀔 때만 쌓는다.
    """

    perfume = models.CharField(max_length=20)
    is_low = models.BooleanField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
