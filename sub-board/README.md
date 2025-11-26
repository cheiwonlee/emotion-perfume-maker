# STM32 LoRa-SubMotor Controller Board

## 개요
STM32에서 SX1272 계열 LoRa 모듈로 작업 명령을 수신하여 4대의 스테핑 모터를 제어  
수신된 Job은 `{ int sensor_id; float rotation_ml; }` 의 구조체 형식이며, rotation_ml × ONE_CYCLE(4096) 만큼 스텝을 수행한다. 작업 완료 후 "DONE" 패킷을 송신한다.

## 하드웨어/핀맵
- UART2: 디버그(115200)
- SPI1: LoRa 통신
- Motor 1: PB13, PB14, PB15, PB1
- Motor 2: PB12, PA11, PA12, PC5
- Motor 3: PC3, PC2, PB0, PA4
- Motor 4: PC12, PC10, PD2, PC11
- Prox 센서: Prox1_Pin, Prox2_Pin (입력, 풀업) (추가 예정)

## 패킷 포맷
- 수신: `[Rx_ID(1)] + [sensor_id:int32][rotation_ml:float32]` (총 1 + sizeof(StepingMotor_t))
- 완료 응답: `[Rx_ID(1)] + "DONE"(4)` (총 5 바이트)

## 소프트웨어 흐름
1. 시작 시 Radio(LoRa) 초기화 및 콜백 등록
2. 메인 루프에서 `Radio.Rx()`로 수신 대기
3. `OnRxDone()`에서 패킷 유효성 검사 후 `g_ReceivedJob`에 복사하고 `g_RunMotorFlag = 1`
4. 메인 루프가 플래그 감지 시 `step_steps()`로 모터 구동
5. 작업 완료 후 "DONE" 패킷 송신

## 주요 함수
- `set_coils(motor_id, a,b,c,d)`: 지정한 모터의 4핀을 제어
- `step_steps(motor_id, steps, delay_ms)`: half-step 시퀀스로 steps만큼 회전
- `OnRxDone(payload, size, rssi, snr)`: 수신 콜백. Buffer 검증 및 job 복사
- `OnTxDone()`: 송신 완료 콜백
