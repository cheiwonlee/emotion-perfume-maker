from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils import timezone # timezone 모듈 임포트
from datetime import timedelta     # timedelta 모듈 임포트

# models.py에서 정의한 두 개의 모델을 import 합니다.
from .models import ProximitySensor as Prox, Status

# 각 향의 이름을 상수로 정의
SCENT_NAMES = ["Lavender", "Cedarwood", "Vanilla", "Bergamot"]

def index(request):
    # 5분 이내에 데이터가 업데이트되어야 ONLINE으로 간주합니다.
    ONLINE_THRESHOLD_MINUTES = 5 
    context = {}
    
    # 1. ProximitySensor 데이터 (수위 센서)
    for name in SCENT_NAMES:
        # 각 센서별 최신 1개 데이터만 가져와서 템플릿 변수로 저장
        # index.html에서는 lavender_list.0.value 등으로 접근합니다.
        context[f"{name.lower()}_list"] = list(Prox.objects.filter(name=name).order_by('-reg_date').values()[:1])

    # 2. Status 데이터 (메인 컨트롤러 제조 상태)
    latest_status_list = list(Status.objects.all().order_by('-reg_date').values()[:1])
    context['latest_status'] = latest_status_list[0] if latest_status_list else None
    
    # 3. 시스템 상태 (ONLINE/OFFLINE) 확인 로직 추가
    context['is_online'] = False
    context['is_waiting_for_data'] = True #  초기 대기 상태 플래그 추가
    
    if context['latest_status']:
        last_reg_date = context['latest_status']['reg_date']
        
        current_time = timezone.now() # 현재 시간 (TZ-aware)
        
        # 현재 시간과 마지막 등록 시간의 차이를 계산합니다.
        time_difference = current_time - last_reg_date
        
        # --- 디버깅 코드 시작: 서버 콘솔에 출력됩니다! ---
        print("--- [TIME DEBUG] ---")
        print(f"1. Last Reg Date (DB): {last_reg_date} (TZ: {last_reg_date.tzinfo})")
        print(f"2. Current Time: {current_time} (TZ: {current_time.tzinfo})")
        print(f"3. Time Difference: {time_difference.total_seconds():.2f} seconds")
        print(f"4. Threshold: {ONLINE_THRESHOLD_MINUTES * 60} seconds")
        print("--------------------")
        # --- 디버깅 코드 끝 ---

        # 시간 차이가 임계값보다 작은지 확인합니다.
        if time_difference < timedelta(minutes=ONLINE_THRESHOLD_MINUTES):
            context['system_status'] = 'ONLINE'
        else:
            # 임계값을 초과하면 OFFLINE
            context['system_status'] = 'OFFLINE (Timeout)'
    else:
        # 데이터가 아예 없는 경우
        context['system_status'] = 'OFFLINE (No Data)'

    # print(f"[DEBUG] Context data for index: {context}") # 디버깅용
    
    return render(request, 'sensor/index.html', context)

# ----------------------------------------------------------------------
# ProximitySensor (수위 센서) API (이하 코드는 수정하지 않았습니다.)
# ----------------------------------------------------------------------

# @csrf_exempt 데코레이터가 필요합니다. (POST 요청 처리 시)
@csrf_exempt
def setProx(request):
    """외부 장치로부터 수위 센서 데이터(Prox)를 수신하여 DB에 저장"""
    if request.method != 'POST':
        return JsonResponse({"message": "Only POST method is allowed"}, status=405)
        
    try:
        # POST 본문에서 데이터 추출
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        raw_value = data.get('value', '').strip()

        # 유효성 검사 및 Boolean 변환
        if not name or name not in SCENT_NAMES:
             return JsonResponse({"message": f"Invalid or missing 'name'. Must be one of {SCENT_NAMES}"}, status=400)

        value = raw_value in ['1', 'true', 'True', 'TRUE', '1.0', 1]
        
        Prox.objects.create(
            name=name,
            value=value
        )
        return JsonResponse({"message": "OK", "received": {"name": name, "value": value}}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"message": "Invalid JSON format"}, status=400)
    except Exception as e:
        return JsonResponse({"message": f"ERROR: {str(e)}"}, status=500)

def getProx(request, cnt):
    """전체 수위 센서 데이터 cnt개 조회"""
    results = list(Prox.objects.all().order_by('-reg_date').values()[:cnt][::-1])
    return JsonResponse(results, safe=False)

def getProxByName(request, name, cnt):
    """특정 수위 센서의 데이터 cnt개 조회"""
    results = list(Prox.objects.filter(name=name).order_by('-reg_date').values()[:cnt][::-1])
    return JsonResponse(results, safe=False)


# ----------------------------------------------------------------------
# Status (시스템 상태) API (이하 코드는 수정하지 않았습니다.)
# ----------------------------------------------------------------------

@csrf_exempt
def setStatus(request):
    """외부 장치로부터 시스템 상태(Status)를 수신하여 DB에 저장"""
    if request.method != 'POST':
        return JsonResponse({"message": "Only POST method is allowed"}, status=405)

    try:
        # POST 본문에서 JSON 데이터 추출
        data = json.loads(request.body)
        
        # 필드가 누락되거나 잘못된 타입인 경우 기본값 처리
        ui_state = data.get('ui_state', 'UNKNOWN')
        mood_name = data.get('mood_name', 'UNKNOWN')
        recipe_L = float(data.get('recipe_L', 0.0))
        recipe_C = float(data.get('recipe_C', 0.0))
        recipe_V = float(data.get('recipe_V', 0.0))
        recipe_B = float(data.get('recipe_B', 0.0))
        
        # 새로운 상태 레코드 생성
        Status.objects.create(
            ui_state=ui_state,
            mood_name=mood_name,
            recipe_L=recipe_L,
            recipe_C=recipe_C,
            recipe_V=recipe_V,
            recipe_B=recipe_B,
        )

        return JsonResponse({
            "message": "Status OK", 
            "received": data
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"message": "Invalid JSON format"}, status=400)
    except Exception as e:
        return JsonResponse({"message": f"ERROR: {str(e)}"}, status=500)


def getStatus(request):
    """최신 시스템 상태(Status) 1개 조회"""
    try:
        # 최신 1개 데이터를 쿼리하여 리스트 형태로 반환
        latest_status_list = list(Status.objects.all().order_by('-reg_date').values()[:1])
        
        if latest_status_list:
            return JsonResponse(latest_status_list[0], safe=False)
        else:
            # 데이터가 없는 경우, 기본 상태 값을 반환
            return JsonResponse({"ui_state": "START", "mood_name": "Ready", "reg_date": ""}, safe=False)

    except Exception as e:
        return JsonResponse({"message": f"Error fetching status: {str(e)}"}, status=500)