# STM32 LoRa-Main Controller Board(Mood Perfume Maker) — 핵심(모터/통신/센서)

## 개요
사용자가 터치 LCD로 무드를 선택하면, 각 향료에 대해 로컬 모터로 병 위치를 맞추고 LoRa로 연결된 주사기 장치에 주입량 (ml)을 요청 -> 주사기가 완료되면 "DONE" 응답을 받아 다음 향료로 진행

## 하드웨어 요약
- UART2: 디버그(115200)
- UART3: 터치 LCD (57600)
- SPI1: LoRa
- 로컬 스테핑 모터: IN1(GPIOA,9), IN2(GPIOB,10), IN3(GPIOB,4), IN4(GPIOB,5)
- LIMIT_SWITCH: GPIOA,12 (풀업)
- PROX_SENSOR: GPIOA,15 (풀업)
- PB7: 터치 인터럽트 신호(풀업)

## 모터
- 구동: half-step 8단계 시퀀스 사용.
- 1회전 = `ONE_CYCLE = 4096` 스텝
- 각도 이동: `steps = (int)(4096 * move_angle / 360)` 계산
- 주요 함수:
  - `SetMotorPins(a,b,c,d)`
  - `MoveMotorSteps(steps, delay_ms)`
  - `MoveToAngle(target_angle)`
  - `ResetMotor()` : 초기 향수통 위치 세팅을 위한 함수

## 통신 (LoRa)
- 초기화: `Radio.Init`, `Radio.SetTxConfig`, `Radio.SetRxConfig`
- 송신 패킷(향료 준비): `[SYRINGE_ID(1)] + StepingMotor_t(sensor_id:int32, rotation_ml:float32)`
- 완료 응답: `[Rx_ID(1)] + "DONE"` (권장: `"DONE\0"` 또는 memcmp로 검사)
- 수신: `OnRxDone()`에서 `Buffer`에 복사 후 `lora_ok_flag` 세팅
