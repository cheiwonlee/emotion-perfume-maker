from django.http import HttpResponse
from .models import ProximitySensor as Prox, DeviceStatus # DeviceStatus 임포트 추가
from django.shortcuts import render
from django.core import serializers
from django.http import JsonResponse
import random
import json
from django.views.decorators.csrf import csrf_exempt # POST 요청을 위해 임시로 추가
from django.conf import settings

# 전역 변수를 사용하여 현재 선택된 기분 코드를 임시 저장 (개발 환경용)
CURRENT_MOOD_ID = '6'

# 새로 추가된 전역 변수: 가장 최근에 처리된 PERFUME 액션 저장 (name, value)
LATEST_PERFUME_ACTION = ('N/A', 'N/A')

# 향료 ID와 이름 매핑 딕셔너리 (임의 지정, C 코드와 일치해야 함)
PERFUME_MAPPING = {
    1: "Lavender", 
    2: "Cedarwood", 
    3: "Vanilla", 
    4: "Bergamot"
}

# 기분 코드 ID와 이름 매핑 딕셔너리
MOOD_NAME_MAPPING = {
    '1': 'Fresh',    # 코드 ID 1 매핑
    '2': 'Calm',     # 코드 ID 2 매핑
    '3': 'Bold',     # 코드 ID 3 매핑
    '4': 'Sweet',    # 코드 ID 4 매핑
    '5': 'Active',   # 코드 ID 5 매핑
    '6': 'Cozy',     # 코드 ID 6 매핑
    '7': 'Mystic',   # 코드 ID 7 매핑
    '8': 'Random',   # 코드 ID 8 매핑
}

# C 프로그램 상태를 한국어 메시지로 번역하는 딕셔너리
C_STATUS_MESSAGES = {
    'SCREEN_START': "화면을 클릭해주세요!",
    'SCREEN_MOODSELECT': "기분 선택 중...",
    'SCREEN_CONFIRM': "기분 선택 확인 대기 중...", # C 코드에는 없지만 예상되는 상태
    'SCREEN_BLENDING': "향수 제조 중...",
    'SCREEN_FINISH': "향수 제조 완료!",
    'N/A': "기기 상태 준비 중...", # 초기 값 또는 알 수 없는 상태
}


def _get_system_status_message():
    """시리얼 연결 상태와 C 프로그램 상태를 통합하여 최종 메시지를 반환합니다."""
    try:
        # 최신 DeviceStatus 레코드를 가져옵니다.
        status_obj = DeviceStatus.objects.latest('reg_date')
    except DeviceStatus.DoesNotExist:
        # DB에 레코드가 없으면 초기 상태 메시지를 반환합니다.
        return "시스템 초기화 중..."
    
    # 1. 시리얼 연결 상태 확인
    if not status_obj.is_serial_connected:
        return "Offline 데이터 수신 대기 중..."
    else:
        # 2. C 프로그램 상태 확인 (연결된 경우에만 C 상태 번역)
        c_status = status_obj.c_screen_status
        return C_STATUS_MESSAGES.get(c_status, f"알 수 없는 상태 ({c_status})")


def index(request):
    # 각 센서의 최신 데이터 1개만 가져옴
    lavender_list = Prox.objects.filter(name="Lavender").order_by('-reg_date').values()[:1]
    cedarwood_list = Prox.objects.filter(name="Cedarwood").order_by('-reg_date').values()[:1]
    vanilla_list = Prox.objects.filter(name="Vanilla").order_by('-reg_date').values()[:1]
    bergamot_list = Prox.objects.filter(name="Bergamot").order_by('-reg_date').values()[:1]

    # DeviceStatus를 가져와서 raw C 상태를 확인합니다. [수정 추가]
    try:
        status_obj = DeviceStatus.objects.latest('reg_date')
        current_c_status = status_obj.c_screen_status
    except DeviceStatus.DoesNotExist:
        current_c_status = 'N/A'

    # 시스템 상태 메시지를 생성합니다.
    system_status_message = _get_system_status_message()

    # 현재 선택된 기분 코드 ID를 이름으로 변환
    global CURRENT_MOOD_ID
    # 매핑된 이름이 없으면 기본 메시지 표시
    current_mood_name = MOOD_NAME_MAPPING.get(CURRENT_MOOD_ID, f"알 수 없는 코드 ({CURRENT_MOOD_ID})")

    # 최근 PERFUME 액션 메시지 생성 
    global LATEST_PERFUME_ACTION
    name, value = LATEST_PERFUME_ACTION

  # 2. C 상태에 따라 latest_perfume_message를 조건부로 설정합니다. [수정 로직]
    if current_c_status != 'SCREEN_BLENDING':
        # 제조(주입) 상태가 아닐 경우 "주입 대기 중"으로 표시
        latest_perfume_message = "주입 대기 중"
    elif name != 'N/A':
        # 제조 상태이면서, LATEST_PERFUME_ACTION에 기록이 있을 경우
        latest_perfume_message = f"{name}을(를) {value}ml 주입 중입니다."
    else:
        # 제조 상태이지만, LATEST_PERFUME_ACTION에 아직 기록이 없을 경우 (초기 상태)
        latest_perfume_message = "최근 주입 액션 없음"

    # 재고 확인
    # 1. 모든 향료의 재고 상태를 확인합니다.
    all_perfumes = [lavender_list, cedarwood_list, vanilla_list, bergamot_list]
    
    # 2. 하나라도 '부족' (value=True) 상태인 센서가 있는지 확인
    # '부족'인 센서가 하나라도 있으면 is_manufacturing_impossible = True
    is_manufacturing_impossible = False
    
    # 데이터가 아예 없는 경우도 제조 불가능으로 간주할 수 있지만, 여기서는 최신 레코드의 value만 확인
    for p_list in all_perfumes:
        if p_list and p_list[0]['value'] == True: # value=True는 '부족'
            is_manufacturing_impossible = True
            break # 하나라도 부족하면 바로 종료
            
    # 최종 제조 상태 메시지 설정
    if is_manufacturing_impossible:
        overall_status_class = "status-bad"
        overall_status_message = "제조 불가능"
        
        # 마지막 업데이트 시간은 모든 리스트 중 가장 최신 시간으로 설정 (옵션)
        # 모든 리스트를 평탄화하고 reg_date를 비교
        all_dates = [p_list[0]['reg_date'] for p_list in all_perfumes if p_list]
        latest_update_time = max(all_dates) if all_dates else "N/A"
        
    else:
        overall_status_class = "status-ok"
        overall_status_message = "제조 가능"
        
        # 모든 센서가 충분할 경우, 마지막 업데이트 시간은 '0'이 전송된 시간일 확률이 높으므로
        # 모든 리스트 중 가장 최신 시간으로 설정
        all_dates = [p_list[0]['reg_date'] for p_list in all_perfumes if p_list]
        latest_update_time = max(all_dates) if all_dates else "N/A"


    context = {
        'lavender_list': lavender_list,
        'cedarwood_list': cedarwood_list,
        'vanilla_list': vanilla_list,
        'bergamot_list': bergamot_list,
        'current_mood_name': current_mood_name,
        'system_status_message': system_status_message, 
        'latest_perfume_message': latest_perfume_message,
        'overall_status_class': overall_status_class,
        'overall_status_message': overall_status_message,
        'latest_overall_update': latest_update_time,
    }

    return render(request, 'index.html', context)

@csrf_exempt
def setDeviceStatus(request):
    """
    Python 시리얼 스크립트로부터 현재 C 프로그램의 상태 및 
    시리얼 연결 상태를 업데이트 받습니다.
    """
    if request.method == 'POST':
        try:
            # 1. request.POST에서 c_status를 읽음
            c_status = request.POST.get('c_status', 'N/A')

            # 2. is_connected 값을 읽고 불리언으로 명시적 변환 (안정성 확보)
            is_connected_str = request.POST.get('is_connected', 'false').lower()
            is_connected = (is_connected_str == 'true')
            
            # DB 레코드를 업데이트 (단일 레코드만 유지)
            status_obj, created = DeviceStatus.objects.get_or_create(
                pk=1, # PK 1번 레코드만 사용 (단일 상태 관리)
                defaults={'c_screen_status': c_status, 'is_serial_connected': is_connected}
            )
            
            if not created:
                # 기존 객체 업데이트
                status_obj.c_screen_status = c_status
                status_obj.is_serial_connected = is_connected
                status_obj.save()

            print(f"[STATUS UPDATE] C={c_status}, Serial={is_connected}")
            return JsonResponse({"message": "OK", "status": c_status, "connected": is_connected}, status=200)
        except Exception as e:
            return JsonResponse({"message": f"Server error: {str(e)}"}, status=500)
    else:
        return JsonResponse({"message": "Method Not Allowed"}, status=405)


def setMood(request):
    """
    dataCollector.py에서 새로운 Mood Code ID(문자열 형태)를 받아 전역 변수에 임시 저장합니다.
    (POST 요청으로 mood_name='7' 전송)
    """

    global CURRENT_MOOD_ID

    if request.method == 'POST':
        try:
            mood_code = request.POST.get('mood_code', 'N/A').strip()
            
            if mood_code in MOOD_NAME_MAPPING:
                CURRENT_MOOD_ID = mood_code
                return JsonResponse({"message": "Mood set successfully", "mood": CURRENT_MOOD_ID}, status=200)
            else:
                return JsonResponse({"message": f"Unknown Mood Code ID: {mood_code}"}, status=400)

        except Exception as e:
            return JsonResponse({"message": f"Server error: {str(e)}"}, status=500)
    else:
        return JsonResponse({"message": "Method Not Allowed"}, status=405)



@csrf_exempt 
def setPerfume(request): # setProx 함수 이름을 setPerfume으로 변경
    """
    PERFUME 센서 데이터를 받아 DB에 저장하고, 최근 주입 액션 상태를 업데이트합니다.
    """
    global LATEST_PERFUME_ACTION # 전역 변수 사용 선언
    
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            # raw_value를 사용하여 전역 변수에 저장 (주입 ml로 표시하기 위해)
            raw_value = request.POST.get('value', '').strip() 

            print(f"[PERFUME RECEIVE] Name: {name}, Value: {raw_value}")
            
            # DB 저장을 위한 Boolean 값 변환 (기존 setProx 로직 유지)
            value = raw_value in ['1', 'true', 'True', 'TRUE', '1.0'] 
            
            # 1. DB에 센서 데이터 저장
            Prox.objects.create(
                name=name,
                value=value
            )
            
            # 2. 전역 상태 업데이트 (index.html 표시용)
            if name and raw_value:
                LATEST_PERFUME_ACTION = (name, raw_value)
            
            return JsonResponse({"message": "OK", "received": {"name": name, "value": raw_value}}, status=200)

        except KeyError as e:
            return JsonResponse({"message": f"KEY_ERROR: {str(e)}"}, status=400)
        except Exception as e:
            return JsonResponse({"message": f"Error saving PROX data: {str(e)}"}, status=500)
    else:
        return JsonResponse({"message": "Method Not Allowed"}, status=405)

@csrf_exempt
def setWaterStatus(request):
    """
    WATER 센서 ID를 받아 해당 향료의 재고 상태를 업데이트합니다.
    센서 ID: 0 (전체 충분), 1~4 (해당 향료 부족)
    """
    if request.method == 'POST':
        try:
            # sensor_id를 정수로 가져옵니다. (기본값 -1)
            sensor_id_str = request.POST.get('sensor_id', '-1').strip()
            
            if not sensor_id_str.isdigit():
                return JsonResponse({"message": "Invalid sensor_id format."}, status=400)
                
            sensor_id = int(sensor_id_str)
            
            if sensor_id == 0:
                # 1. 센서 ID가 0인 경우: 모든 향료를 '충분' (value=False)로 설정
                for name in PERFUME_MAPPING.values():
                    Prox.objects.create(name=name, value=False)
                message = "All perfumes set to Sufficient."
                
            elif sensor_id in PERFUME_MAPPING:
                # 2. 센서 ID가 1~4인 경우: 해당 향료를 '부족' (value=True)로 설정
                name = PERFUME_MAPPING[sensor_id]
                Prox.objects.create(name=name, value=True)
                message = f"Perfume '{name}' set to Insufficient."
                
            else:
                return JsonResponse({"message": f"Unknown Sensor ID: {sensor_id}"}, status=400)

            return JsonResponse({"message": "OK", "status": message, "id": sensor_id}, status=200)

        except Exception as e:
            return JsonResponse({"message": f"Server error: {str(e)}"}, status=500)
    else:
        return JsonResponse({"message": "Method Not Allowed"}, status=405)

def getProx(request, cnt):
    results = list(Prox.objects.all().order_by('-reg_date').values()[:cnt][::-1])
    return JsonResponse(results, safe=False)


def getProxByName(request, name, cnt):
    results = list(Prox.objects.filter(name=name).order_by('-reg_date').values()[:cnt][::-1])
    return JsonResponse(results, safe=False)