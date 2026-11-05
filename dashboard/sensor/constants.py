"""
보드 펌웨어와 맞춰야 하는 값들을 한 곳에 모아 둔다.
(예전에는 views.py 안에 딕셔너리로 흩어져 있었다)
"""

# sensor_id → 향료 이름. 보드의 sensor_id(1~4)와 같다.
PERFUMES = {1: "Lavender", 2: "Cedarwood", 3: "Vanilla", 4: "Bergamot"}
PERFUME_IDS = {name: sid for sid, name in PERFUMES.items()}

# 기분 코드 → (영문 이름, 화면에 보여줄 설명). main.c 의 moodNames[] 순서와 같다.
MOODS = {
    1: ("Fresh", "상쾌한 날"),
    2: ("Calm", "차분한 날"),
    3: ("Bold", "자신 있는 날"),
    4: ("Sweet", "달콤한 날"),
    5: ("Active", "활기찬 날"),
    6: ("Cozy", "포근한 날"),
    7: ("Mystic", "깊고 신비로운 날"),
    8: ("Random", "무작위"),
}

# 기분별 레시피 (ml) — main-board/Core/Src/main.c 의 RunBlendingProcess() 와 같아야 한다.
RECIPES = {
    1: {"Lavender": 1, "Cedarwood": 1, "Vanilla": 1, "Bergamot": 4},
    2: {"Lavender": 8, "Cedarwood": 4, "Vanilla": 2, "Bergamot": 2},
    3: {"Lavender": 2, "Cedarwood": 6, "Vanilla": 2, "Bergamot": 4},
    4: {"Lavender": 4, "Cedarwood": 2, "Vanilla": 8, "Bergamot": 2},
    5: {"Lavender": 2, "Cedarwood": 2, "Vanilla": 2, "Bergamot": 10},
    6: {"Lavender": 4, "Cedarwood": 4, "Vanilla": 8, "Bergamot": 2},
    7: {"Lavender": 1, "Cedarwood": 4, "Vanilla": 1, "Bergamot": 1},
}

# 보드 화면 상태 → 대시보드 문구
SCREEN_START = "SCREEN_START"
SCREEN_MOODSELECT = "SCREEN_MOODSELECT"
SCREEN_CONFIRM = "SCREEN_CONFIRM"
SCREEN_BLENDING = "SCREEN_BLENDING"
SCREEN_FINISH = "SCREEN_FINISH"

SCREEN_TEXT = {
    SCREEN_START: "손님을 기다리고 있어요",
    SCREEN_MOODSELECT: "오늘의 기분을 고르는 중",
    SCREEN_CONFIRM: "고른 기분을 확인하는 중",
    SCREEN_BLENDING: "향수를 섞는 중",
    SCREEN_FINISH: "향수가 완성됐어요",
}
