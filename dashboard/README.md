# Web Dashboard

향수 제조기의 상태를 실시간으로 보여 주는 Django 웹 대시보드와, 보드의 시리얼 출력을 서버로 옮기는 수집기입니다.
전체 실행 방법은 [레포 루트 README](../README.md) 를 보세요. (`python run.py` 한 줄이면 됩니다)

## 화면에서 볼 수 있는 것

- **오늘의 기분과 레시피** — 보드에서 고른 기분, 그 레시피(ml), 지금 어떤 향료를 넣는 중인지
- **향료 통** — 수위 센서 값(충분/부족). 가상 보드로 실행하면 실제 잔량(ml)까지 보여 줌
- **제조 기록** — 언제 어떤 기분으로 몇 ml 를 만들었는지, 향료 비율 막대, 오늘 만든 병 수
- **가상 터치 LCD** — 가상 보드로 실행했을 때만 나타나며, 눌러서 보드를 조작

화면은 1초마다 `GET /sensor/api/state` 를 받아 필요한 부분만 다시 그립니다. (페이지 새로고침 없음)

## 구조

```
dashboard/
├── dataCollector.py          시리얼 → 서버 수집기 (parse_line / Collector)
├── iotProject/settings.py
├── sensor/
│   ├── constants.py          향료·기분·레시피·화면 상태 (펌웨어와 맞춰야 하는 값)
│   ├── models.py             DeviceStatus, Blend, Injection, StockEvent
│   ├── services.py           이벤트 → DB 반영, 대시보드 상태 조회
│   ├── views.py / urls.py    API
│   ├── mock_bridge.py        가상 보드와 연결 (run.py 로 실행할 때만)
│   ├── templates/sensor/dashboard.html
│   └── tests.py
└── static/                   dashboard.css, dashboard.js
```

## 데이터 모델

| 모델 | 내용 |
|------|------|
| `DeviceStatus` | 보드 화면 상태, 시리얼 연결, 선택된 기분, 마지막 신호 시각 (레코드 1개) |
| `Blend` | 향수 한 병 제조 (시작·종료 시각, 완성/중단) |
| `Injection` | 제조 중 향료 하나를 넣은 기록 (향료, ml) |
| `StockEvent` | 수위 센서 값이 바뀐 기록 (향료, 부족 여부) |

## API

| 경로 | 메소드 | 보내는 쪽 | 내용 |
|------|-------|----------|------|
| `/sensor/setDeviceStatus` | POST | 수집기 | `c_status`, `is_connected` (화면 상태 없이 오면 heartbeat) |
| `/sensor/setMood` | POST | 수집기 | `mood_code` 1~8 |
| `/sensor/setPerfume` | POST | 수집기 | `name`, `value`(ml) |
| `/sensor/setWaterStatus` | POST | 수집기 | `sensor_id` 0 = 전체 충분, 1~4 = 해당 향료 부족 |
| `/sensor/api/state` | GET | 화면 | 대시보드에 필요한 상태 전부 (JSON) |
| `/sensor/api/mock/press` · `tank` · `auto` | POST | 화면 | 가상 LCD 누르기, 향료 통 비우기/채우기, 자동 시연 |

## 시리얼 프로토콜 (보드 → 수집기)

```
STATUS : SCREEN_BLENDING     화면 상태 (SCREEN_START / MOODSELECT / CONFIRM / BLENDING / FINISH)
MOOD : 2                     선택한 기분 번호
PERFUME : Lavender : 4       넣은 향료와 양(ml)
WATER_X : 3                  3번 향료 부족
WATER_O : 0                  모든 향료 충분
```

## 테스트

```bash
python manage.py test
```
