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
- 송신 패킷(향료 준비): `[PACKET_ID(1)=121] + StepingMotor_t(sensor_id:int32, rotation_ml:float32)`
- 송신이 끝난 뒤(`OnTxDone`) 수신으로 전환해 서브보드 응답을 기다림 — `WaitForSyringeReply(timeout_ms)`
  - `[ID] + "DONE" + [수위]` → 완료. 수위 1 이면 `WATER_O : n`, 0 이면 `WATER_X : n` 출력
  - `[ID] + "LOW" + [sensor_id]` → 향료 부족. `WATER_X : n` 출력 후 제조 중단, LCD 에 "Refill needed" 표시
  - 시간 초과(주입량 × 4096 × 2ms + 10초) → 제조 중단, LCD 에 "No reply" 표시
- 중단되면 회전판을 원위치로 돌리고 기분 선택 화면으로 돌아감
- 수위 조회 `QueryLevels()`: `[ID]"LVL?"` 를 보내고 `[ID]"LVL"[통1~4]` 응답을 `WATER_X/O : n` 으로 출력
  - 부팅 직후, 시작 화면에 들어올 때, 시작 화면에서 30초마다 실행 (통을 다시 채운 것도 반영됨)

## 대시보드용 시리얼 출력 (UART2)
```
STATUS : SCREEN_START | SCREEN_MOODSELECT | SCREEN_CONFIRM | SCREEN_BLENDING | SCREEN_FINISH
MOOD : 2
PERFUME : Lavender : 4
WATER_X : 3        (3번 향료 부족)
WATER_O : 3        (3번 향료 충분)
```
newlib-nano 의 float `printf` 가 꺼져 있으므로 숫자는 모두 `%d` 로 출력합니다.
