# 🎄 Daily Mood Perfume Maker - Web Dashboard

사용자 기분 맞춤형 스마트 향수 제조 시스템의 **실시간 웹 대시보드**입니다.

> 컴퓨터과학전공 3학년 2학기 **사물인터넷프로그래밍** 기말 프로젝트 (7조)

## 📋 프로젝트 개요

이 프로젝트는 사용자가 터치 LCD를 통해 기분(Mood)을 선택하면, 해당 감정에 어울리는 향수 레시피에 따라 향수를 즉석에서 제조해주는 IoT 시스템입니다. 본 저장소는 시스템의 **웹 대시보드** 부분으로, 하드웨어 상태와 제조 과정을 실시간으로 모니터링할 수 있습니다.

### 시스템 아키텍처

```
┌─────────────┐    LoRa     ┌─────────────┐
│  Main Board │ ◄────────► │  Sub Board  │
│  (STM32)    │             │  (STM32)    │
└──────┬──────┘             └─────────────┘
       │ Serial (USB)              │
       ▼                           ▼
┌─────────────┐              스테핑 모터
│ dataCollector│              (향료 주입)
│   (Python)  │
└──────┬──────┘
       │ HTTP POST
       ▼
┌─────────────┐
│   Django    │
│  Web Server │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Dashboard  │
│ (index.html)│
└─────────────┘
```

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| **실시간 상태 모니터링** | 시리얼 연결 상태, C 프로그램 화면 상태를 실시간 동기화 |
| **향료 재고 관리** | 4종 향료(Lavender, Cedarwood, Vanilla, Bergamot)의 수위 감지 및 부족 알림 |
| **기분(Mood) 표시** | 사용자가 선택한 기분 코드를 대시보드에 시각화 |
| **제조 과정 디스플레이** | 현재 주입 중인 향료 종류 및 주입량 실시간 표시 |
| **재고 변화 그래프** | Flot.js를 활용한 향료별 재고 변화 추이 차트 |

## 🛠 기술 스택

### Backend
- **Django 4.x** - Python 웹 프레임워크
- **SQLite** - 데이터베이스

### Frontend
- **HTML5 / CSS3** - 대시보드 UI
- **JavaScript / jQuery** - DOM 조작 및 비동기 처리
- **Flot.js** - 실시간 데이터 시각화 차트

### Middleware
- **Python** - 시리얼 통신 및 HTTP 요청 처리
- **pySerial** - STM32와 시리얼 통신
- **Requests** - Django 서버로 HTTP POST 전송

## 📁 프로젝트 구조

```
.
├── manage.py              # Django 프로젝트 관리 스크립트
├── dataCollector.py       # 시리얼 데이터 수집 및 서버 전송 스크립트
├── db.sqlite3             # SQLite 데이터베이스
│
├── sensor/                # Django 앱 디렉토리
│   ├── admin.py           # Django Admin 설정
│   ├── apps.py            # 앱 설정 (SensorConfig)
│   ├── models.py          # 데이터 모델 정의
│   ├── urls.py            # URL 라우팅
│   └── views.py           # 뷰 함수 (API 엔드포인트)
│
├── templates/
│   └── index.html         # 대시보드 메인 페이지
│
└── iotProject/            # Django 프로젝트 설정
    └── settings.py
```

## 📊 데이터 모델

### ProximitySensor
비접촉 수위 센서 데이터를 저장합니다.
| 필드 | 타입 | 설명 |
|------|------|------|
| `name` | CharField | 향료 이름 (Lavender, Cedarwood, Vanilla, Bergamot) |
| `value` | BooleanField | 재고 상태 (False: 충분, True: 부족) |
| `reg_date` | DateTimeField | 등록 시간 |

### DeviceStatus
기기의 현재 상태를 추적합니다.
| 필드 | 타입 | 설명 |
|------|------|------|
| `c_screen_status` | CharField | C 프로그램 화면 상태 |
| `is_serial_connected` | BooleanField | 시리얼 연결 상태 |
| `reg_date` | DateTimeField | 마지막 업데이트 시간 |

### Mood
선택된 기분 코드를 저장합니다.
| 필드 | 타입 | 설명 |
|------|------|------|
| `mood_name` | CharField | 기분 이름 (Fresh, Calm, Bold 등) |
| `reg_date` | DateTimeField | 등록 시간 |

## 🔌 API 엔드포인트

| 엔드포인트 | 메소드 | 설명 |
|------------|--------|------|
| `/sensor/` | GET | 대시보드 메인 페이지 |
| `/sensor/setPerfume` | POST | 향료 주입 데이터 저장 |
| `/sensor/setMood` | POST | 선택된 기분 코드 업데이트 |
| `/sensor/setDeviceStatus` | POST | 기기 상태 업데이트 |
| `/sensor/setWaterStatus` | POST | 수위 센서 상태 업데이트 |
| `/sensor/getProxByName/<name>/<cnt>` | GET | 특정 향료의 최근 데이터 조회 |

## 🚀 실행 방법

### 1. 필수 패키지 설치
```bash
pip install django pyserial requests
```

### 2. 데이터베이스 마이그레이션
```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Django 서버 실행
```bash
python manage.py runserver
```

### 4. 시리얼 데이터 수집기 실행
```bash
python dataCollector.py
```

### 5. 브라우저에서 대시보드 접속
```
http://127.0.0.1:8000/sensor/
```

## 🎨 향수 레시피

시스템은 8가지 기분(Mood)에 따른 사전 정의된 레시피를 제공합니다:

| 코드 | 기분 | Lavender | Cedarwood | Vanilla | Bergamot |
|------|------|----------|-----------|---------|----------|
| 1 | Fresh (상쾌함) | 1 | 1 | 1 | 4 |
| 2 | Calm (차분함) | 4 | 2 | 1 | 1 |
| 3 | Bold (자신감) | 1 | 3 | 1 | 2 |
| 4 | Sweet (달콤함) | 2 | 1 | 4 | 1 |
| 5 | Active | - | - | - | - |
| 6 | Cozy | - | - | - | - |
| 7 | Mystic | - | - | - | - |
| 8 | Random | - | - | - | - |

## 📡 시리얼 통신 프로토콜

`dataCollector.py`는 STM32에서 전송되는 다음 형식의 로그를 파싱합니다:

```
STATUS : SCREEN_BLENDING     # 화면 상태
PERFUME : Lavender : 1.0     # 향료명 : 주입량(ml)
MOOD : 2                     # 선택된 기분 코드
WATER_X : 1                  # 1번 향료 부족 경고
WATER_O : 1                  # 모든 향료 충분
```


*2025년 12월 | 사물인터넷프로그래밍 7조*
