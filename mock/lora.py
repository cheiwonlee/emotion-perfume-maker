"""
가상 LoRa 무선 채널.

실제 SX1272 대신, 같은 채널(주파수)에 있는 노드끼리 bytes 패킷을 주고받게 해 준다.
- 보낸 노드 자신은 패킷을 받지 않는다 (실제 무선과 동일)
- airtime_ms 만큼 지연 후 도착
- loss_rate 확률로 패킷이 사라진다 (통신 오류 테스트용)
"""
import random
import threading
import time


class VirtualLoRaChannel:
    def __init__(self, airtime_ms: float = 30, loss_rate: float = 0.0, log=None):
        self.airtime_ms = airtime_ms
        self.loss_rate = loss_rate
        self.log = log or (lambda msg: None)
        self._nodes = []

    def attach(self, node: "VirtualRadio"):
        self._nodes.append(node)

    def transmit(self, sender: "VirtualRadio", packet: bytes):
        def deliver():
            time.sleep(self.airtime_ms / 1000)
            if random.random() < self.loss_rate:
                self.log(f"[LoRa] 패킷 유실 ({sender.name} → {len(packet)}B)")
                return
            for node in self._nodes:
                if node is not sender:
                    node._on_air(packet)

        threading.Thread(target=deliver, daemon=True).start()


class VirtualRadio:
    """
    SX1272 드라이버(Radio.Send / Radio.Rx / RxDone 콜백)를 흉내 내는 객체.

    on_rx_done(payload) 콜백을 등록하면 패킷이 도착할 때 호출된다.
    """

    def __init__(self, name: str, channel: VirtualLoRaChannel):
        self.name = name
        self.channel = channel
        self.on_rx_done = None
        channel.attach(self)

    def send(self, packet: bytes):
        self.channel.transmit(self, bytes(packet))

    def _on_air(self, packet: bytes):
        if self.on_rx_done:
            self.on_rx_done(packet)
