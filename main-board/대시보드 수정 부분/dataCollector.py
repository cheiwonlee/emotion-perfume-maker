import serial
import serial.tools.list_ports
import requests
import random, time

ports = serial.tools.list_ports.comports()

print("=== Available COM Ports ===")
for port in ports:
    print(f"Port: {port.device}")
    print(f"Description: {port.description}")
    print(f"HWID: {port.hwid}")
    print("---------------------------")

flag = False

while True:
    time.sleep(0.1)
    portName = input("Enter the port name:")
    if portName == "test":
        flag = True
        break
    try:
        ser = serial.Serial(
            port=portName,
            baudrate=115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=0
        )
        break
    except:
        print("Invaild Value")

while True:
    time.sleep(0.1)

    # ------------ TEST MODE -------------
    if flag:
        try:
            data = {
                'name': 'Lavender',             # 테스트일 때 기본값
                'value': random.randint(0, 1)
            }
            print(requests.post("http://localhost:8000/sensor/setProx", data=data).json())
        except:
            print("Could not connect Web Server")
        time.sleep(0.5)
        continue


    # ------------ SENSOR MODE -------------
    if ser.readable():
        smo = ser.readline().decode().strip()
        print("RAW:", smo)

        # Expected: "Lavender : 1"
        msg = smo.split(" : ")
        if len(msg) != 2:
            print("Invalid sensor format")
            continue

        name = msg[0]      # Lavender
        value = msg[1]     # 1

        # 데이터 패킷 준비
        data = {
            'name': name,
            'value': value
        }

        try:
            print(requests.post("http://localhost:8000/sensor/setProx", data=data).json())
        except:
            print("Could not connect Web Server")
