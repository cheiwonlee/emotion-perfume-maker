# STM32 LoRa-SubMotor Controller Board

## 개요
STM32에서 SX1272 계열 LoRa 모듈로 작업 명령을 수신하여 4대의 스테핑 모터를 제어  
수신된 Job은 `{ int sensor_id; float rotation_ml; }` 의 구조체 형식이며, rotation_ml × ONE_CYCLE(4096) 만큼 스텝을 수행한다. 작업 완료 후 "DONE" 패킷을 송신한다.

## 하드웨어/핀맵
- UART2: 디버그(115200)
- SPI1: LoRa 통신
- Motor 1 (Lavender): PB13, PB14, PB15, PB1 — CubeMX 에서 설정
- Motor 2 (Cedarwood): PB12, PA11, PA12, PC5 — `ExtraMotorPins_Init()` 에서 설정
- Motor 3 (Vanilla): PC3, PC2, PB0, PA4 — `ExtraMotorPins_Init()` 에서 설정
- Motor 4 (Bergamot): PC12, PC10, PD2, PC11 — `ExtraMotorPins_Init()` 에서 설정
- 수위 센서: `LEVEL_SENSORS[]` 표. 현재 1번(Lavender) 통 = PB2(`Prox`) 만 연결, LOW 신호 = 액체 감지
  - 다른 통에 센서를 달면 표의 해당 칸에 `{ 포트, 핀 }` 을 넣고 CubeMX 에서 그 핀을 GPIO_Input 으로 설정
  - 센서가 없는 통은 '알 수 없음'으로 보고되어 대시보드에 표시되지 않음

## 패킷 포맷
- `Rx_ID` = 121 (메인보드 `PACKET_ID` 와 같아야 함)
- 수신: `[Rx_ID(1)] + [sensor_id:int32][rotation_ml:float32]` (총 9 바이트)
- 완료 응답: `[Rx_ID(1)] + "DONE"(4) + [주입 후 수위(1)]` (총 6 바이트, 수위 1 충분 / 0 부족 / 0xFF 센서 없음)
- 부족 응답: `[Rx_ID(1)] + "LOW"(3) + [sensor_id(1)]` (총 5 바이트) — 모터를 돌리지 않음

## 소프트웨어 흐름
1. 시작 시 Radio(LoRa) 초기화 및 콜백 등록
2. 메인 루프에서 `Radio.Rx()`로 수신 대기
3. `OnRxDone()`(인터럽트)에서는 패킷을 검사해 `g_job` 에 복사하고 `g_job_pending = 1` 만 세팅
4. 메인 루프가 `RunJob()` 실행: 수위 확인 → 모터 구동 → 응답 송신
   - 인터럽트 안에서 모터를 돌리면 안 되는 이유: SysTick 과 EXTI 우선순위가 같아 `HAL_Delay` 가 끝나지 않음
5. 응답 송신이 끝나면(`OnTxDone`) 다시 수신 대기

## 주요 함수
- `RunJob(job)`: 수위 확인, 모터 구동, DONE/LOW 응답
- `ReadLevel(sensor_id)`: 수위 센서 값 (LEVEL_OK / LEVEL_LOW / LEVEL_UNKNOWN)
- `set_coils(motor_id, a,b,c,d)`: 지정한 모터의 4핀을 제어 (`MOTOR_PINS[]` 표)
- `step_steps(motor_id, steps, delay_ms)`: half-step 시퀀스로 회전, 끝나면 코일 전류 차단
- `OnRxDone(payload, size, rssi, snr)`: 수신 콜백. 작업만 받아 두고 바로 반환
