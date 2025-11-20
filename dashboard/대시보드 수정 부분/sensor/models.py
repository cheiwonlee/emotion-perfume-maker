from django.db import models
from django.utils import timezone

# 비접촉 수위 센서 테이블
class ProximitySensor(models.Model):
	name = models.CharField(max_length=20)
	reg_date = models.DateTimeField(editable=False)
	value = models.BooleanField()
	def save(self, *args, **kwargs):
		if not self.id:
			self.reg_date = timezone.now()
		return super(ProximitySensor, self).save(*args, **kwargs)

