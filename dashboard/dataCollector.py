import serial
import serial.tools.list_ports
import requests
import random, time
import threading
from collections import deque
import json # JSON 사용을 위해 추가

# --- 설정 및 초기화 ---
ports = serial.tools.list_ports.comports()

print("=== Available COM Ports ===")
for port in ports:
    print(f"Port: {port.device}")
    print(f"Description: {port.description}")
    print(f"HWID: {port.hwid}")
    print("---------------------------")

# --- 전역 상태 변수 ---
SERIAL_CONNECTED = False # 시리얼 연결 상태 (False: Offline, True: Connected)
C_SCREEN_STATUS = 'N/A' # C 프로그램에서 보낸 마지막 스크린 상태 (초기값)
DJANGO_STATUS_URL = 'http://127.0.0.1:8000/sensor/setDeviceStatus' # Django 상태 업데이트 URL
DJANGO_MOOD_URL = 'http://127.0.0.1:8000/sensor/setMood'
# [추가] WATER 센서 데이터 전송 URL
DJANGO_WATER_URL = 'http://127.0.0.1:8000/sensor/setWaterStatus'

ser = None
# 시리얼 포트 찾기 및 열기
for port in ports:
    try:
        # 이전에 연결에 성공한 포트를 사용하거나 적절한 포트 설정을 유지합니다.
        ser = serial.Serial(port.device, 115200, timeout=1) 
        SERIAL_CONNECTED = True # 연결 성공
        print(f"Connected to {port.device}")
        break
    except serial.SerialException:
        print(f"Failed to open {port.device}")
        continue
if not SERIAL_CONNECTED:
    print("No serial port connected or accessible. Running in offline mode.")

# 데이터 버퍼와 락
data_buffer = deque()
buffer_lock = threading.Lock()
MAX_BUFFER_SIZE = 10  # 최대 10개까지 버퍼링

# --- 상태 전송 함수 ---
def send_status_update(c_status, is_connected):
    """Django 서버에 현재 C 상태 및 시리얼 연결 상태를 전송"""
    try:
        payload = {
            'c_status': c_status,
            'is_connected': str(is_connected).lower()
        }
        # POST 요청을 JSON 형식으로 전송
        response = requests.post(DJANGO_STATUS_URL, data=payload, timeout=0.5) 
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생
        # print(f"[STATUS SENT] C:{c_status}, Conn:{is_connected} -> OK")
    except requests.exceptions.RequestException as e:
        # Django 서버가 꺼져있거나 네트워크 오류 시
        print(f"[STATUS ERROR] Failed to send status to Django: {e}")

# --- 데이터 전송 함수 ---
def send_buffered_data():
    # 별도 스레드에서 버퍼링된 데이터를 전송
    global data_buffer
    
    while True:
        time.sleep(0.1)  # 100ms마다 확인
        
        with buffer_lock:
            if not data_buffer:
                continue
            
            # 버퍼에서 데이터 꺼내기 
            data_type, name, value = data_buffer.popleft() 

            url = None
            payload = None
            
            try:
                if data_type == 'MOOD':
                    # 기분 코드는 /sensor/setMood 엔드포인트로 전송
                    url = "http://127.0.0.1:8000/sensor/setMood"
                    # views.py의 setMood 함수는 'mood_name' 필드를 기대함
                    payload = {'mood_code': value}
                elif data_type == 'PERFUME':
                    url = "http://127.0.0.1:8000/sensor/setPerfume"
                    payload = {'name': name, 'value': value}
                    # 센서 데이터는 /sensor/setPerume 엔드포인트로 전송
                elif data_type == 'WATER':
                    # sensor_id = buffer_data[1]
                    sensor_id = name
                    url = "http://127.0.0.1:8000/sensor/setWaterStatus"
                    payload = {'sensor_id': sensor_id}
                else:
                    continue # 알 수 없는 타입 무시
                
                response = requests.post(url, data=payload, timeout=0.5)
                print(f"[SENT][{data_type}] {payload} -> {response.json()}")
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] {data_type} data send failed: {e}")



# --- 기분 읽기 함수 ---
def send_mood_update(mood_code):
    """
    C 프로그램에서 보낸 MOOD 코드를 Django 서버로 전송합니다.
    """
    try:
        data = {
            'mood_code': mood_code
        }
        # POST 요청으로 MOOD 코드 전송
        response = requests.post(DJANGO_MOOD_URL, data=data)
        
        if response.status_code == 200:
            print(f"[SERVER] Mood update successful: {mood_code}")
        else:
            print(f"[SERVER] Mood update failed. Code: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"[SERVER] Error connecting to Django server for mood: {e}")




# --- 시리얼 읽기 함수 ---
def read_serial_data():
    # 시리얼 포트에서 데이터를 읽고 버퍼에 저장
    global ser, SERIAL_CONNECTED, C_SCREEN_STATUS
    
    status_update_timer = time.time() # 상태 업데이트 주기 타이머
    STATUS_UPDATE_INTERVAL = 1.0 # 1초마다 상태를 Django로 전송

    while True:
        try:
            if ser and SERIAL_CONNECTED:
                # 1. 시리얼 데이터 읽기
                raw_data = ser.readline().decode('utf-8').strip()
                
                
                if raw_data:
                    
                    # 2. 프로그램 상태 (STATUS) 파싱 및 업데이트
                    # Touch LCD 함수에서 로그를 보냄.
                    # Draw_Screen_Start(), Draw_Screen_MoodSelect(), Draw_Screen_MoodSelect()
                    # , Draw_Screen_Blending(), Draw_Screen_Finish().
                    # 필요 시 추가 예정
                    if raw_data.startswith("STATUS : "):
                        new_status = raw_data.split(' : ')[1].strip()
                        if new_status != C_SCREEN_STATUS:
                            C_SCREEN_STATUS = new_status
                            print(f"[PARSED][STATUS] C_SCREEN_STATUS={C_SCREEN_STATUS}")
                            # 상태가 바뀔 때마다 즉시 전송
                            send_status_update(C_SCREEN_STATUS, SERIAL_CONNECTED)

                    # 3. PERFUME 센서 데이터 파싱 및 버퍼링 
                    elif raw_data.startswith("PERFUME:"):
                        parts = raw_data.split(':')
                        # printf(parts)
                        if len(parts) >= 3:
                            name = parts[1].strip() # 향료명
                            value = parts[2].strip()    # 주입 ml
                            if len(data_buffer) < MAX_BUFFER_SIZE:
                                data_buffer.append(('PERFUME', name, value))
                            else:
                                print(f"[WARNING] Buffer full, dropping oldest data")
                                data_buffer.popleft()
                                data_buffer.append(('PERFUME', name, value))
                        else:
                            print(f"[ERROR] PERFUME parse failed: expected 3 parts, got {len(parts)}")
                    
                    # 4. MOOD 
                    elif raw_data.startswith("MOOD : "):
                        parts = raw_data.split(' : ')
                        if len(parts) == 2:
                            mood_name = parts[1].strip()
                            print(f"[PARSED][MOOD] mood_name={mood_name}")
                            
                            with buffer_lock:
                                if len(data_buffer) < MAX_BUFFER_SIZE:
                                    # (type, name, value) 형식으로 저장. name은 None
                                    data_buffer.append(('MOOD', None, mood_name)) 
                                else:
                                    print(f"[WARNING] Buffer full, dropping oldest data")
                                    data_buffer.popleft() 
                                    data_buffer.append(('MOOD', None, mood_name))
                        else:
                            print(f"[ERROR] MOOD parse failed: expected 2 parts, got {len(parts)}")

                    # 5. PROX (수위 감지 여부)
                    elif raw_data.startswith("WATER_X : "):
                        parts = raw_data.split(' : ')
                        if len(parts) == 2:
                            sensor_id_str = parts[1].strip()
                            if sensor_id_str.isdigit():
                                sensor_id = int(sensor_id_str)
                                
                                with buffer_lock:
                                    if len(data_buffer) < MAX_BUFFER_SIZE:
                                        # 버퍼에 ('WATER', 센서번호) 저장
                                        data_buffer.append(('WATER', sensor_id, None)) 
                                    else:
                                        print(f"[WARNING] Buffer full, dropping oldest data")
                                        data_buffer.popleft()
                                        data_buffer.append(('WATER', sensor_id, None))
                    
                # [새로운 로직 추가] 6. WATER_O (수위 감지 여부 - 충분)
                    elif raw_data.startswith("WATER_O : "):
                        parts = raw_data.split(' : ')
                        if len(parts) == 2:
                            sensor_id_str = parts[1].strip() # 1~4 중 하나가 들어오지만
                            if sensor_id_str.isdigit():
                                 # Django views.py의 setWaterStatus 함수에 따라, ID 0을 보내면 
                                # 모든 향료가 '충분' 상태로 업데이트됩니다.
                                sensor_id_to_send = 0 

                                with buffer_lock:
                                    if len(data_buffer) < MAX_BUFFER_SIZE:
                                        # 버퍼에 ('WATER', 0, None) 저장
                                        data_buffer.append(('WATER', sensor_id_to_send, None)) 
                                    else:
                                        print(f"[WARNING] Buffer full, dropping oldest data")
                                        data_buffer.popleft()
                                        data_buffer.append(('WATER', sensor_id_to_send, None))
                            else:
                                print(f"[ERROR] WATER_O parse failed: expected 2 parts, got {len(parts)}")
    
                        
                
                #  주기적으로 시리얼 연결 상태 전송 (연결 확인 목적)
                if time.time() - status_update_timer >= STATUS_UPDATE_INTERVAL:
                    send_status_update(C_SCREEN_STATUS, SERIAL_CONNECTED)
                    status_update_timer = time.time()
                
            else:
                # 시리얼 연결이 끊어졌거나 처음부터 연결되지 않았을 경우
                if SERIAL_CONNECTED:
                    # 연결이 끊어진 경우
                    SERIAL_CONNECTED = False
                    print("[SERIAL] Connection lost.")
                    # 연결 끊김 상태를 즉시 전송
                    send_status_update(C_SCREEN_STATUS, SERIAL_CONNECTED)
                
                # 비연결 상태에서는 1초마다 상태 전송을 시도합니다.
                if time.time() - status_update_timer >= STATUS_UPDATE_INTERVAL:
                    send_status_update(C_SCREEN_STATUS, SERIAL_CONNECTED)
                    status_update_timer = time.time()
                    
                time.sleep(1) # 시리얼 연결이 없으면 1초 대기
                
        except serial.SerialException as se:
            print(f"[ERROR] Serial device communication error: {se}")
            if SERIAL_CONNECTED:
                SERIAL_CONNECTED = False
                print("[SERIAL] Connection status changed to disconnected.")
                send_status_update(C_SCREEN_STATUS, SERIAL_CONNECTED)
            time.sleep(1) 
        except Exception as e:
            print(f"[ERROR] Unexpected error in read_serial_data: {e}")
            time.sleep(1) 

# --- 메인 실행 ---
# 데이터 전송 스레드 시작
sender_thread = threading.Thread(target=send_buffered_data)
sender_thread.daemon = True 
sender_thread.start()

# 시리얼 읽기 루프 시작
read_serial_data()