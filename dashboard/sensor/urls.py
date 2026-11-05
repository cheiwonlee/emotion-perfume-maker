from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    
    # 센서 데이터 저장(POST 요청) - setProx -> setPerfume으로 이름 변경 및 반영
    path('setPerfume', views.setPerfume, name='setPerfume'),

    # Mood Code 저장(POST 요청)
    path('setMood', views.setMood, name='setMood'), 
    
    # **새로 추가: C 프로그램 및 시리얼 상태 업데이트 엔드포인트**
    path('setDeviceStatus', views.setDeviceStatus, name='setDeviceStatus'),
    
    # [추가] WATER 센서 상태 업데이트 엔드포인트
    path('setWaterStatus', views.setWaterStatus, name='setWaterStatus'),

    path('getProxByName/<str:name>/<int:cnt>', views.getProxByName, name='getProxByName'),
]