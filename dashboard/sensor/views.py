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
    # DB에서 직접 슬라이싱 (Python에서 모든 데이터를 가져오는 것 방지)
    results = list(Prox.objects.all().order_by('-reg_date').values()[:cnt][::-1])
    return JsonResponse(results, safe=False)

def setProx(request):
    try:
        name = request.POST.get('name', '').strip()
        raw_value = request.POST.get('value', '').strip()
        
        print(f"[DEBUG] name={repr(name)}, raw_value={repr(raw_value)}, type={type(raw_value)}")

        # 문자열을 Boolean으로 변환 (더 정확한 비교)
        value = raw_value in ['1', 'true', 'True', 'TRUE', 1, '1.0']
        
        print(f"[DEBUG] Converted value={value}")

        Prox.objects.create(
            name=name,
            value=value
        )
        return JsonResponse({"message": "OK", "received": {"name": name, "value": value}}, status=200)

    except KeyError as e:
        return JsonResponse({"message": f"KEY_ERROR: {str(e)}"}, status=400)
    except Exception as e:
        return JsonResponse({"message": f"ERROR: {str(e)}"}, status=500)


def getProxByName(request, name, cnt):
    # DB에서 직접 제한하여 쿼리 최적화
    results = list(
        Prox.objects.filter(name=name)
        .order_by('-reg_date')
        .values()[:cnt]
    )[::-1]

    return JsonResponse(results, safe=False)
