# 🎄 Daily Mood Perfume Maker

터치 LCD에서 오늘의 기분을 고르면, 기분에 맞는 레시피로 향료 4종(Lavender · Cedarwood · Vanilla · Bergamot)을 섞어 향수를 만들어 주는 IoT 시스템입니다.

> 컴퓨터과학전공 3학년 2학기 **사물인터넷프로그래밍** 기말 프로젝트 (7조)
> 원본: [tmdgns5136/IOT-Programming7](https://github.com/tmdgns5136/IOT-Programming7) — 브랜치별로 나뉘어 있던 코드를 한 레포에 폴더별로 모았습니다.

## 📁 폴더 구성

| 폴더 | 원래 브랜치 | 내용 |
|------|------------|------|
| [`dashboard/`](dashboard/) | `Feat/DashBoard` | Django 웹 대시보드 + 시리얼 수집기(`dataCollector.py`) |
| [`main-board/`](main-board/) | `Feat/MainBoard` | STM32F446 메인보드 — 터치 LCD UI, 회전판 모터, LoRa 마스터 (STM32CubeIDE 프로젝트) |
| [`sub-board/`](sub-board/) | `Feat/SubBoard` | STM32F446 서브보드 — LoRa로 명령을 받아 주사기 모터 구동 (STM32CubeIDE 프로젝트) |
| [`mock/`](mock/) | (새로 추가) | 위 하드웨어 전체를 흉내 내는 **가상 보드** — 부품 없이 시스템 전체를 실행 |
| `run.py` | (새로 추가) | 전체 실행기 — 명령 하나로 웹 서버·가상 보드·수집기를 함께 실행 |
| `tests/` | (새로 추가) | 가상 보드 테스트 |

각 브랜치의 커밋 기록은 해당 폴더 아래로 옮겨 그대로 보존했습니다. (`git log -- main-board/` 로 확인 가능)

## 🧩 시스템 구조

```
 [터치 LCD] ──UART3── Main Board ◄──── LoRa 922.1MHz ────► Sub Board ── 주사기 모터 ×4
                       │ 회전판 모터                                    (향료 주입)
                       │ 수위 센서
                       │
                    UART2 (USB 시리얼, 115200)
                       ▼
               dataCollector.py ──HTTP POST──► Django ──► 대시보드 (http://127.0.0.1:8000/sensor/)
```

## 🚀 실행

```bash
pip install -r requirements.txt
python run.py
```

이게 전부입니다. DB 준비 → 웹 서버 → 가상 보드 → 수집기가 한 번에 켜지고 브라우저에 대시보드가 열립니다.
대시보드 오른쪽 아래 **가상 터치 LCD** 를 눌러 기분을 고르고 Start 를 누르면, 향료 통의 잔량이 줄고 레시피 진행과 제조 기록이 실시간으로 바뀝니다. 향료 통 아래 `비우기` 로 재고 부족 상황도 만들어 볼 수 있습니다.

| 명령 | 설명 |
|------|------|
| `python run.py` | 가상 보드로 실행 (부품 필요 없음) |
| `python run.py --auto` | 자동 시연을 켠 채로 시작 |
| `python run.py --speed 1` | 실제 보드와 같은 속도 (기본은 5배속) |
| `python run.py --real` | 실제 보드를 USB 로 연결해서 실행 (`--serial COM3` 으로 포트 지정) |
| `python run.py --port 8001` | 웹 서버 포트 변경 |
| `python -m mock` | 대시보드 없이 터미널에서 가상 보드만 (시리얼 출력·LoRa 로그 확인용) |

그 밖의 가상 보드 옵션: `--loss 0.2` (LoRa 패킷 20% 유실), `--sub-id 20` (아래 ID 불일치 재현), `--capacity 30` (향료 통 용량 ml)

### 가상 보드(mock)는 어떻게 동작하나요?

수집기는 실제로는 `serial.Serial` 로 보드를 읽습니다. 가상 보드는 같은 `readline()` 을 가진 **가상 시리얼**을 제공하므로, 수집기와 Django 는 실제 보드를 쓸 때와 같은 코드로 동작합니다.

| 파일 | 대응하는 실제 부품 / 코드 |
|------|-------------------------|
| `mock/main_board.py` | `main-board/Core/Src/main.c` — 화면 상태 머신, 터치 키 해석, 레시피, 회전판 이동, DONE 대기 |
| `mock/sub_board.py` | `sub-board/Core/Src/main.c` — 패킷 검사, `ml × 4096` 스텝 회전, DONE 응답 |
| `mock/protocol.py` | LoRa 패킷 형식 — C 구조체와 바이트 단위로 동일 |
| `mock/lora.py` | SX1272 LoRa 모듈 (지연·유실) |
| `mock/hardware.py` | 스테핑 모터, 향료 통 + 수위 센서, 터치 LCD |
| `mock/serial_port.py` | UART2 (USB 시리얼) |
| `mock/runtime.py` | 대시보드의 가상 LCD 버튼과 가상 보드를 연결 |

### 실제 보드로 실행하기

1. `main-board/`, `sub-board/` 를 STM32CubeIDE 에서 열어 빌드하고 보드에 올립니다.
2. 메인보드를 USB 로 연결하고 `python run.py --real` 을 실행합니다.

## 🧪 테스트

```bash
cd dashboard && python manage.py test     # 대시보드 + 수집기 파서 (12개)
python -m unittest discover tests         # 가상 보드 (5개)
```
GitHub 에 push 하면 Actions 에서 자동으로 실행됩니다.

## 🔍 코드 리뷰 — 무엇을 왜 바꿨나

**대시보드 (Django)**
- **상태를 전역 변수에 저장** → 기분·최근 주입이 `views.py` 전역 변수에 있어서 서버를 재시작하면 사라지고, 프로세스가 둘 이상이면 서로 다른 값을 보였습니다. 모두 DB(`DeviceStatus`, `Blend`, `Injection`)로 옮겼습니다.
- **'제조'라는 개념이 데이터에 없음** → 주입 기록이 흩어져 있어 "몇 시에 어떤 향수를 만들었는지"를 알 수 없었습니다. `Blend` 모델로 제조 한 번을 묶어 제조 기록과 오늘 만든 병 수를 보여 줍니다.
- **주입량이 재고 테이블에 Boolean 으로 저장** → 1ml 를 넣으면 그 향료가 '부족'으로 표시되던 버그. 재고는 수위 센서 값만, 그것도 값이 바뀔 때만 기록합니다.
- **views.py 에 로직이 몰려 있음** → 처리 로직을 `services.py`, 펌웨어와 맞춰야 하는 값은 `constants.py` 로 분리했습니다. 테스트하기 쉬워졌습니다.
- **잘못된 입력에도 200 응답 / 500 으로 예외 노출** → 입력 검증 후 400, GET 으로 부르면 405.
- **보안 설정** → CSRF 미들웨어를 통째로 꺼 두었고 `SECRET_KEY` 가 코드에 박혀 있었습니다. CSRF 는 켜고 보드용 엔드포인트만 예외 처리했고, 키·DEBUG 는 환경변수로 받습니다. 쓰이지 않던 `django-cors-headers` 는 뺐습니다.
- **마이그레이션 충돌** → 번호가 겹치는 마이그레이션 때문에 `migrate` 가 실패했습니다. 새 모델 기준으로 하나로 정리했습니다.

**화면 (프론트엔드)**
- `<meta refresh="1">` 로 1초마다 페이지 전체를 새로고침해서 깜빡이고, 차트가 매번 초기화됐습니다. JSON API 를 1초마다 받아 바뀐 부분만 다시 그립니다.
- 차트 스크립트가 `$.ajax` 결과를 기다리지 않고 이전 데이터를 그리는 비동기 버그가 있었습니다. (fetch → 렌더 순서로 정리)
- 쓰지 않는 템플릿, jQuery·Flot 라이브러리 사본(예제 폴더 포함)을 지웠습니다. 외부 라이브러리 없이 동작합니다.
- 디자인: 향수 공방의 향료 병을 모티브로 다시 만들었습니다. 향료 통은 실제 잔량만큼 액체가 차 있고, 각 향료의 실제 색을 씁니다. 모바일에서도 깨지지 않습니다.

**수집기 (dataCollector.py)**
- 파일을 import 하기만 해도 포트를 열고 무한 루프가 돌았습니다. 함수(`parse_line`)와 클래스(`Collector`)로 나눠 테스트하고 `run.py` 에서 재사용합니다.
- 이벤트 종류에 따라 바로 보내기/버퍼에 넣기가 섞여 있어 서버 도착 순서가 바뀔 수 있었습니다. 큐 하나로 순서를 보장합니다.
- 락을 잡은 채로 HTTP 요청을 해서 시리얼 읽기가 막힐 수 있었고, `PERFUME` 은 락 없이 버퍼에 넣었습니다. `queue.Queue` 로 바꿨습니다.
- 서버가 꺼져 있으면 같은 오류를 1초마다 출력했습니다. 끊길 때 한 번, 복구될 때 한 번만 알립니다.
- 포트를 아무거나 먼저 열리는 것으로 골랐습니다. STM32(ST-Link) 포트를 우선 찾고 `--serial` 로 지정할 수 있습니다.
- 쓰이지 않던 `send_mood_update()` 를 지웠습니다.

**펌웨어 (C)** — 수정하지 않았고, 확인이 필요한 점을 아래에 정리했습니다.

## 🗂 기타 정리

- 빌드 결과물(`Debug/*.o`), `__pycache__`, `db.sqlite3`, 빈 `최신 버전` 파일은 기록에서 제외하고 `.gitignore` 에 등록했습니다.

## ⚠️ 실제 보드에서 확인이 필요한 점

mock 을 만들면서 코드끼리 맞지 않는 부분을 발견했습니다.

1. **LoRa ID 불일치** — 메인보드는 `PACKET_ID = 121`, 서브보드는 `Rx_ID = 20` 입니다. 이대로면 서브보드가 모든 패킷을 무시하고 메인보드는 DONE 을 계속 기다립니다. (`--sub-id 20` 으로 재현 가능)
2. **대시보드용 시리얼 출력이 펌웨어에 없음** — 수집기는 `STATUS : …`, `MOOD : …`, `PERFUME : …`, `WATER_X/O : …` 줄을 기다리지만 `main-board/main.c` 에는 이 `printf` 가 없습니다. mock 은 이 줄을 출력하고 있으니, 실제 보드에서 대시보드를 쓰려면 아래처럼 추가해야 합니다.
   ```c
   // Draw_Screen_Start() 등 각 화면 함수 끝에
   printf("STATUS : SCREEN_START\n");        // SCREEN_MOODSELECT / SCREEN_CONFIRM / SCREEN_BLENDING / SCREEN_FINISH
   // ProcessTouch() 에서 기분이 정해졌을 때
   printf("MOOD : %d\n", mood);
   // LavenderMove() 등에서 Radio.Send() 직전에
   printf("PERFUME : Lavender : %d\n", (int)ml);
   // 수위 센서: 부족하면 해당 번호, 모두 충분하면 0
   printf("WATER_X : %d\n", sensor_id);   printf("WATER_O : 0\n");
   ```
3. **서브보드 모터 2~4번 핀 미연결** — `set_coils()` 에 1번 모터 핀만 구현돼 있습니다.
4. **레시피 표 불일치** — `dashboard/README.md` 의 레시피 표와 `main.c` 의 실제 레시피 값이 다릅니다. mock 은 `main.c` 값을 따릅니다.
