from django.db import models

class ProximitySensor(models.Model):
    # Proximity Sensor Model (수위 센서)
    name = models.CharField(max_length=50) # 향 이름 (Lavender, Cedarwood, etc.)
    value = models.BooleanField(default=False) # 수위 상태 (True: 부족/Empty, False: 정상/Full)
    reg_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}: {'부족' if self.value else '정상'} ({self.reg_date.strftime('%Y-%m-%d %H:%M:%S')})"

    class Meta:
        ordering = ['-reg_date']
        # verbose_name = "수위 센서 데이터"


class Status(models.Model):
    # System Status Model (스테핑 모터 및 제조 상태)
    
    # UI에 표시될 현재 제조 단계
    # START: 대기 중, BLENDING_L: 라벤더 제조 중, FINISH: 완료 등
    ui_state = models.CharField(max_length=50, default='START') 
    
    # 현재 제조 중인 향 이름
    mood_name = models.CharField(max_length=100, default='Ready') 
    
    # 레시피 데이터 (각 오일의 필요량)
    recipe_L = models.FloatField(default=0.0)
    recipe_C = models.FloatField(default=0.0)
    recipe_V = models.FloatField(default=0.0)
    recipe_B = models.FloatField(default=0.0)
    
    reg_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"상태: {self.ui_state}, 무드: {self.mood_name}, 레시피: L={self.recipe_L}ml"

    class Meta:
        ordering = ['-reg_date']
        # verbose_name = "시스템 상태"