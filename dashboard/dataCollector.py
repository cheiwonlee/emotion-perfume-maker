import serial
import serial.tools.list_ports
import requests
import time
import threading
from collections import deque



# -------------------- [상수 및 초기 설정] --------------------
# 데이터 버퍼와 락 (잔량 센서 데이터 전송을 비동기 처리하기 위함)
data_buffer = deque()
buffer_lock = threading.Lock()
MAX_BUFFER_SIZE = 10 
# -----------------------------------------------------------

ports = serial.tools.list_ports.comports()

print("=== 사용 가능한 COM 포트 ===")
for port in ports:
    print(f"포트: {port.device}")
    print(f"설명: {port.description}")
    print(f"HWID: {port.hwid}")
    print("---------------------------")


flag = False
ser = None

ser = None

def send_buffered_data():
    """
    별도 스레드에서 버퍼링된 (잔량 센서) 데이터를 웹 서버로 전송합니다.
    잔량 센서는 'setProx' 엔드포인트를 사용합니다.
    """
    global data_buffer
    
    while True:
        time.sleep(0.1) 
        
        with buffer_lock:
            if not data_buffer:
                continue
            
            # 버퍼에서 데이터 꺼내기: (name, value)
            name, value = data_buffer.popleft()
        
        # 락 해제 후 네트워크 요청 (논블로킹)
        try:
            # 잔량 센서는 setProx 엔드포인트로 전송 (name, value)
            data = {'name': name, 'value': int(value)}
            # print(f"[INFO] Sending setProx: {data}")
            response = requests.post("http://localhost:8000/sensor/setProx", json=data, timeout=2)
            # print(f"[SENT PROX] -> {response.status_code}")
        except Exception as e:
            print(f"[ERROR] setProx Web Server error: {e}")
            # 전송 실패 시 버퍼에 다시 넣기 (재시도)
            with buffer_lock:
                # 맨 앞에 다시 넣어 재시도
                data_buffer.appendleft((name, value))

# 백그라운드 전송 스레드 시작
sender_thread = threading.Thread(target=send_buffered_data, daemon=True)
sender_thread.start()
time.sleep(0.1)

# 사용자로부터 포트 이름 입력 받기
portName = input("연결할 COM 포트 이름을 입력하세요 (예: COM3, /dev/ttyUSB0): ")

# 시리얼 포트 연결 시도
try:
    ser = serial.Serial(
        port=portName,
        baudrate=115200,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=0.5 
    )
    print(f"[INFO] {portName}에 연결되었습니다.")
except Exception as e:
    print(f"[ERROR] 포트를 열 수 없습니다: {e}")
    ser = None

# 메인 루프: 시리얼 데이터 수신 및 전송
while True:
    try:
        if ser is None or not ser.is_open:
            print("[ERROR] 시리얼 포트가 열려있지 않습니다. 0.5초 후 재시도합니다.")
            time.sleep(0.5)
            continue

        # 시리얼로부터 한 줄 읽기
        raw = ser.readline()
        if not raw:
            # 읽을 데이터가 없으면 잠깐 대기
            time.sleep(0.05)
            continue

        try:
            # UTF-8로 디코딩 시도
            line = raw.decode('utf-8', errors='ignore').strip()
        except Exception:
            # 디코딩 실패 시 문자열로 변환
            line = str(raw).strip()

        if not line:
            continue

        print(f"[RAW] {repr(line)}")

        # ===============================================
        # 1. STATUS 메시지 처리 로직 (제조 상태 및 레시피)
        # 예: STATUS: ui_state=BLENDING_L, mood_name=Fresh, recipe_L=1.0, ...
        if line.startswith("STATUS:"):
            try:
                data_str = line.replace("STATUS:", "", 1).strip()
                parts = data_str.split(',')
                    
                # 딕셔너리 형태로 파싱하여 POST 요청 데이터 준비
                new_status = {}
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        # key를 소문자로 변환하고 값의 공백 제거
                        new_status[key.strip().lower()] = value.strip()
                        
                # 레시피 데이터의 키 이름 통일 (recipe_L -> recipe_l)
                # 메인보드에서 recipe_L, recipe_C 등으로 보냈다면, 웹 대시보드 모델(models.py)에 맞게 조정 필요
                # Django model: recipe_L, recipe_C, ...
                
                # 시리얼에서 L, C, V, B 형태로 받았다고 가정하고, 웹 대시보드 모델에 맞춰 key 수정
                if 'l' in new_status:
                    new_status['recipe_L'] = float(new_status.pop('l'))
                if 'c' in new_status:
                    new_status['recipe_C'] = float(new_status.pop('c'))
                if 'v' in new_status:
                    new_status['recipe_V'] = float(new_status.pop('v'))
                if 'b' in new_status:
                    new_status['recipe_B'] = float(new_status.pop('b'))

                print(f"[STATUS] Parsed: {new_status}")
                        
                # STATUS 데이터 웹 서버로 전송 (setStatus 엔드포인트 사용)
                response = requests.post("http://localhost:8000/sensor/setStatus", json=new_status, timeout=2)
                try:
                    print(f"[SENT STATUS] -> {response.status_code} {response.json()}")
                except Exception:
                    print(f"[SENT STATUS] -> {response.status_code} (no json)")
            except Exception as e:
                print(f"[ERROR] Status parse/send error: {e}")
                
            continue # STATUS 메시지 처리 후 다음 루프

        # ===============================================
        # 2. 잔량 센서 데이터 처리 로직 
        # 예: "Lavender : 1" (부족) 또는 "Bergamot : 0" (정상)
        if " : " not in line:
            # STATUS 메시지도 아니고 센서 데이터 형식도 아닌 경우
            # print(f"[WARN] Unknown format: {line}")
            continue
            
        msg = line.split(" : ")
        if len(msg) != 2:
            print(f"[ERROR] Parse failed: expected 2 parts, got {len(msg)}")
            continue

        name = msg[0].strip()
        value_str = msg[1].strip()

        # 유효성 검사: 수위 상태는 0 (정상) 또는 1 (부족)
        if value_str not in ['0', '1']:
            print(f"[ERROR] Invalid value: {value_str}")
            continue

        value = int(value_str)
        print(f"[PARSED] name={name}, value={value}")

        # 버퍼에 데이터 추가 (논블로킹)
        with buffer_lock:
            if len(data_buffer) < MAX_BUFFER_SIZE:
                data_buffer.append((name, value))
                print(f"[BUFFERED] Added to buffer (size: {len(data_buffer)}/{MAX_BUFFER_SIZE})")
            else:
                print(f"[WARNING] Buffer full, dropping oldest data")
                data_buffer.popleft()
                data_buffer.append((name, value))

    except Exception as e:
        print(f"[ERROR] Main loop error: {e}")
        time.sleep(0.1)