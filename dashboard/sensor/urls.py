from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    
    path('getProx/<int:cnt>', views.getProx, name='getProx'),
    # 센서 데이터 저장(POST 요청)
    path('setProx', views.setProx, name='setProx'),
    path('getProxByName/<str:name>/<int:cnt>', views.getProxByName, name='getProxByName'),

]
