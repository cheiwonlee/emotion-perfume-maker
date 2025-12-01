from django.urls import path

from . import views

urlpatterns = [
    # 웹 대시보드 메인 페이지
    path('', views.index, name='index'), 
    
    # -----------------------------------------------------
    # ProximitySensor (수위 센서) 관련 경로 - 이전 버전 호환용
    path('getProx/<int:cnt>', views.getProx, name='getProx'),
    path('setProx', views.setProx, name='setProx'),
    path('getProxByName/<str:name>/<int:cnt>', views.getProxByName, name='getProxByName'),
    # -----------------------------------------------------
    
    # Status (시스템 상태) 관련 새로운 경로
    # 아두이노/외부 장치에서 제조 상태를 업데이트할 때 사용
    path('setStatus', views.setStatus, name='setStatus'), 
    
    # UI에서 현재 상태(latest_status)를 비동기적으로 가져올 때 사용
    path('getStatus', views.getStatus, name='getStatus'), 
]