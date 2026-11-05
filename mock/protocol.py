"""
LoRa 패킷 형식 — main-board/Core/Src/main.c, sub-board/Core/Src/main.c 와 바이트 단위로 동일하게 맞춘 것.

C 코드의 구조체:
    typedef struct {
        int   sensor_id;     // 4바이트 (리틀엔디언, STM32)
        float rotation_ml;   // 4바이트
    } StepingMotor_t;

패킷 종류
    작업 지시 (메인 → 서브) : [ID(1)] + [sensor_id:int32][rotation_ml:float32]   총 9바이트
    시작 신호 (메인 → 서브) : [ID(1)] + "START" + [mood(1)]                    총 7바이트
    완료 응답 (서브 → 메인) : [ID(1)] + "DONE"                                 총 5바이트
"""
import struct

# 메인보드 PACKET_ID 와 서브보드 Rx_ID (둘 다 121).
# 예전 sub-board 코드는 20 이라 통신이 안 됐다. --sub-id 20 으로 실행하면 그때 상황을 재현할 수 있다.
PACKET_ID = 121

JOB_STRUCT = struct.Struct("<if")          # int32 + float32, 리틀엔디언
JOB_PACKET_SIZE = 1 + JOB_STRUCT.size      # 9
DONE_PAYLOAD = b"DONE"

# sensor_id ↔ 향료 이름 (dashboard/sensor/views.py 의 PERFUME_MAPPING 과 동일)
PERFUMES = {1: "Lavender", 2: "Cedarwood", 3: "Vanilla", 4: "Bergamot"}

# 기분 번호 ↔ 이름 (main.c 의 moodNames[])
MOOD_NAMES = ["NULL", "Fresh", "Calm", "Bold", "Sweet", "Active", "Cozy", "Mystic", "Random"]


def build_job_packet(packet_id: int, sensor_id: int, rotation_ml: float) -> bytes:
    """main.c 의 PrepareTxPacket() 과 동일"""
    return bytes([packet_id]) + JOB_STRUCT.pack(sensor_id, rotation_ml)


def parse_job_packet(packet: bytes):
    """sub-board OnRxDone() 에서 하는 memcpy(&received_data, Buffer + 1, ...) 와 동일"""
    sensor_id, rotation_ml = JOB_STRUCT.unpack(packet[1:JOB_PACKET_SIZE])
    return sensor_id, rotation_ml


def build_start_packet(packet_id: int, mood: int) -> bytes:
    """main.c 의 SendStartCommand() 와 동일"""
    return bytes([packet_id]) + b"START" + bytes([mood])


def build_done_packet(packet_id: int) -> bytes:
    return bytes([packet_id]) + DONE_PAYLOAD


def is_done_packet(packet: bytes, expected_id: int) -> bool:
    """main.c: Buffer[0] == Rx_ID && size >= 5 && strncmp(Buffer+1, "DONE", 4) == 0"""
    return len(packet) >= 5 and packet[0] == expected_id and packet[1:5] == DONE_PAYLOAD
