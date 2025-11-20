from django.http import HttpResponse
from .models import ProximitySensor as Prox
from django.shortcuts import render
from django.core import serializers
from django.http import JsonResponse
import random
import json

def index(request):
    lavender_list = Prox.objects.filter(name="Lavender").order_by('-reg_date').values()[:1]
    cedarwood_list = Prox.objects.filter(name="Cedarwood").order_by('-reg_date').values()[:1]
    vanilla_list = Prox.objects.filter(name="Vanilla").order_by('-reg_date').values()[:1]
    bergamot_list = Prox.objects.filter(name="Bergamot").order_by('-reg_date').values()[:1]
    
    context = {
        'lavender_list': lavender_list,
        'cedarwood_list': cedarwood_list,
        'vanilla_list': vanilla_list,
        'bergamot_list': bergamot_list,
    }
    
    return render(request, 'sensor/index.html', context)

def getProx(request, cnt):
    results = list(Prox.objects.all().order_by('-reg_date').values())[:cnt][::-1]
    return JsonResponse(results, safe=False)

def setProx(request):
    try:
        name = request.POST['name']
        raw_value = request.POST['value']

        # 문자열을 Boolean으로 변환
        value = True if raw_value in ['1', 'true', 'True'] else False

        Prox.objects.create(
            name=name,
            value=value
        )
        return JsonResponse({"message": "OK"}, status=200)

    except KeyError:
        return JsonResponse({"message": "KEY_ERROR"}, status=400)


def getProxByName(request, name, cnt):
    results = list(
        Prox.objects.filter(name=name)
        .order_by('-reg_date')
        .values()
    )[:cnt][::-1]

    return JsonResponse(results, safe=False)
