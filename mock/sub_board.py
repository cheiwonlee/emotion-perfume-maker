"""
서브보드(주사기 모터 보드) mock — sub-board/Core/Src/main.c 의 동작을 그대로 옮긴 것.

1. LoRa 로 작업 패킷 [ID][sensor_id][rotation_ml] 을 기다린다
2. ID 와 패킷 길이가 맞으면 해당 모터를 rotation_ml × 4096 스텝 돌린다 (스텝당 1ms)
3. 다 돌면 [ID]"DONE" 을 돌려보낸다
"""
import queue
import threading

from . import protocol
from .hardware import VirtualStepperMotor


class SubBoard:
    STEP_DELAY_MS = 1  # main.c: delay_per_step = 1

    def __init__(self, radio, clock, tanks, rx_id=protocol.PACKET_ID, log=None):
        self.radio = radio
        self.clock = clock
        self.tanks = tanks
        self.rx_id = rx_id
        self.log = log or (lambda msg: None)
        self.motors = {sid: VirtualStepperMotor(f"syringe-{sid}", clock) for sid in protocol.PERFUMES}
        self._rx_queue = queue.Queue()
        radio.on_rx_done = self._rx_queue.put  # OnRxDone 콜백 등록

    def start(self):
        threading.Thread(target=self._loop, name="sub-board", daemon=True).start()
        return self

    def _loop(self):
        while True:
            self.log("Waiting for Job...")
            packet = self._rx_queue.get()
            self.on_rx_done(packet)

    def on_rx_done(self, packet: bytes):
        # main.c: if (Buffer[PHYMAC_PDUOFFSET_RXID] == Rx_ID)
        if packet[0] != self.rx_id:
            self.log(f"> ID 불일치로 무시 (받은 ID={packet[0]}, 내 ID={self.rx_id})")
            return
        # main.c: if (BufferSize == (1 + sizeof(StepingMotor_t)))
        if len(packet) != protocol.JOB_PACKET_SIZE:
            self.log(f"> 작업 패킷이 아님 ({len(packet)}B) — 무시")  # START 패킷이 여기에 해당
            return

        sensor_id, ml = protocol.parse_job_packet(packet)
        steps = int(ml * VirtualStepperMotor.ONE_CYCLE)
        name = protocol.PERFUMES.get(sensor_id, "?")
        self.log(f"> Job: sensor_id={sensor_id}({name}), {ml:.2f}ml → {steps} steps")

        motor = self.motors.get(sensor_id)
        if motor:
            motor.move_steps(steps, self.STEP_DELAY_MS)
            self.tanks.take(sensor_id, ml)

        self.radio.send(protocol.build_done_packet(self.rx_id))
        self.log("'DONE' sent. Waiting for next command.")
