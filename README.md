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

## 🚀 부품 없이 실행하기 (mock)

```bash
pip install -r requirements.txt

# 터미널 1 — 웹 서버
cd dashboard
python manage.py migrate
python manage.py runserver

# 터미널 2 — 가상 보드 + 수집기
cd dashboard
python dataCollector.py --mock --auto
```

브라우저에서 <http://127.0.0.1:8000/sensor/> 를 열면 가상 보드가 향수를 만드는 과정(화면 상태, 기분, 주입 중인 향료, 재고 부족/충분)이 실시간으로 바뀝니다.

`--auto` 없이 실행하면 키보드로 가상 터치 LCD를 직접 누를 수 있습니다.

| 입력 | 동작 |
|------|------|
| `t` | 화면 터치 (START / FINISH 화면에서 다음으로) |
| `1`~`8` | 기분 선택 (1 Fresh · 2 Calm · 3 Bold · 4 Sweet · 5 Active · 6 Cozy · 7 Mystic · 8 Random) |
| `s` / `b` | 확인 화면의 [Start] / [Back] |
| `m 2` | 기분 하나를 처음부터 끝까지 한 번에 실행 |
| `drain 3` / `refill` | 3번 향료 통 비우기 / 전부 채우기 → 대시보드 재고 표시 확인 |
| `levels` | 향료 통 잔량 보기 |
| `auto` | 자동 시연 켜기/끄기 |

대시보드 없이 보드 동작만 보고 싶다면 레포 루트에서 `python -m mock` 을 실행하세요. 메인보드 시리얼 출력(`[UART]`)과 서브보드 로그(`[SUB]`)가 함께 보입니다.

### mock 옵션

| 옵션 | 기본값 | 설명 |
|------|-------|------|
| `--speed` | `5` | 시뮬레이션 배속. `1` 이면 실제 보드와 같은 속도 (8ml 주입 ≈ 33초) |
| `--loss` | `0` | LoRa 패킷 유실 확률 (0~1). 유실되면 실제 펌웨어처럼 DONE을 무한히 기다림 |
| `--sub-id` | `121` | 서브보드 LoRa ID. `20` 을 주면 현재 sub-board 코드의 ID 불일치를 재현 |
| `--capacity` | `30` | 향료 통 하나의 용량(ml) |
| `--verbose` | – | (`dataCollector.py`) 가상 보드의 시리얼 출력도 화면에 표시 |

### mock 은 어떻게 동작하나요?

`dataCollector.py` 는 원래 `serial.Serial` 로 보드를 읽습니다. `--mock` 을 주면 같은 `readline()` 을 가진 **가상 시리얼**(`mock/serial_port.py`)을 대신 넣어 주기 때문에, 수집기와 Django 코드는 실제 보드를 쓸 때와 똑같이 동작합니다.

| 파일 | 대응하는 실제 부품 / 코드 |
|------|-------------------------|
| `mock/main_board.py` | `main-board/Core/Src/main.c` — 화면 상태 머신, 터치 키 해석, 레시피, 회전판 이동, DONE 대기 |
| `mock/sub_board.py` | `sub-board/Core/Src/main.c` — 패킷 검사, `ml × 4096` 스텝 회전, DONE 응답 |
| `mock/protocol.py` | LoRa 패킷 형식 (`[ID][int32 sensor_id][float32 ml]`, `[ID]"DONE"`) — C 구조체와 바이트 단위로 동일 |
| `mock/lora.py` | SX1272 LoRa 모듈 (지연·유실 시뮬레이션) |
| `mock/hardware.py` | 스테핑 모터, 향료 통 + 수위 센서, 터치 LCD |
| `mock/serial_port.py` | UART2 (USB 시리얼) |

## 🔧 실제 보드로 실행하기

1. `main-board/`, `sub-board/` 를 각각 STM32CubeIDE 에서 열어 빌드 후 보드에 업로드합니다.
2. 메인보드를 USB로 PC에 연결하고 `python dataCollector.py` 를 실행합니다.

## ✏️ 통합하면서 바꾼 것

- **Django 마이그레이션 정리** — 번호가 겹치는 마이그레이션(`0003`·`0004` 가 두 개씩)이 있어 `migrate` 가 실패하던 문제를, 현재 모델 기준 `0001_initial.py` 하나로 다시 만들었습니다.
- **재고가 잘못 '부족'으로 뜨던 문제** — `setPerfume` 이 주입량을 재고 테이블에 Boolean 으로 저장해서, 1ml 주입 시 해당 향료가 '부족'으로 표시됐습니다. 재고는 수위 센서(`setWaterStatus`)만 기록하도록 고쳤습니다.
- `dataCollector.py` — `--mock` 옵션 추가, `PERFUME : 이름 : 양` 형식(README 표기)도 인식하도록 수정.
- `setMood` 에 `@csrf_exempt` 추가 (다른 POST 엔드포인트와 통일).
- 빌드 결과물(`Debug/*.o` 등), `__pycache__`, `db.sqlite3`, 빈 `최신 버전` 파일은 기록에서 제외하고 `.gitignore` 에 등록했습니다. 펌웨어는 CubeIDE 에서 빌드하면, DB 는 `migrate` 하면 다시 생깁니다.
- 펌웨어(`.c`) 코드는 수정하지 않았습니다.

## ⚠️ 실제 보드에서 확인이 필요한 점

mock 을 만들면서 코드끼리 맞지 않는 부분을 발견했습니다.

1. **LoRa ID 불일치** — 메인보드는 `PACKET_ID = 121`, 서브보드는 `Rx_ID = 20` 입니다. 이대로면 서브보드가 모든 패킷을 무시하고 메인보드는 DONE 을 계속 기다립니다. (`--sub-id 20` 으로 재현 가능)
2. **대시보드용 시리얼 출력이 펌웨어에 없음** — `dataCollector.py` 는 `STATUS : …`, `MOOD : …`, `PERFUME : …`, `WATER_X/O : …` 줄을 기다리지만 `main-board/main.c` 에는 이 `printf` 가 없습니다. mock 은 이 줄을 출력하고 있으니, 실제 보드에서 대시보드를 쓰려면 아래처럼 추가해야 합니다.
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
