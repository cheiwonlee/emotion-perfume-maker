from django.db import models
from django.utils import timezone


# 비접촉 수위 센서 테이블 (ProximitySensor)
# name: 센서 이름 (예: 'Lavender', 'Cedarwood')
# value: 재고 상태 (False: 충분, True: 부족/없음)
class ProximitySensor(models.Model):
	name = models.CharField(max_length=20)
	reg_date = models.DateTimeField(editable=False)
	value = models.BooleanField()
    
	def save(self, *args, **kwargs):
		# 새로운 객체인 경우에만 등록 시간을 현재 시간으로 설정
		if not self.id:
			self.reg_date = timezone.now()
		return super(ProximitySensor, self).save(*args, **kwargs)
    
	class Meta:
		verbose_name_plural = "Proximity Sensors"

# 기기 상태 테이블 (C 프로그램의 스크린 상태 및 시리얼 연결 상태 추적)
class DeviceStatus(models.Model):
    # C 프로그램에서 보내는 스크린 상태 (예: 'SCREEN_START')
    c_screen_status = models.CharField(max_length=50, default='SCREEN_START', verbose_name="C Program Status")
    
    # 시리얼 포트 연결 상태 (Python 스크립트가 주기적으로 업데이트)
    is_serial_connected = models.BooleanField(default=False, verbose_name="Serial Connected")
    
    # 마지막 업데이트 시간
    reg_date = models.DateTimeField(auto_now=True, verbose_name="Last Update Time")
    
    class Meta:
        verbose_name_plural = "Device Status"

# 기분 코드 저장 테이블
class Mood(models.Model):
    # '행복', '편안', '집중', 또는 '2' 등
    mood_name = models.CharField(max_length=50) 
    reg_date = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            self.reg_date = timezone.now()
        return super(Mood, self).save(*args, **kwargs)