// 보드 ↔ 대시보드 약속. dashboard/sensor/constants.py, dashboard/dataCollector.py 의 parse_line 과 같은 내용이다.

export const PERFUMES = { 1: "Lavender", 2: "Cedarwood", 3: "Vanilla", 4: "Bergamot" };
export const PERFUME_IDS = Object.fromEntries(Object.entries(PERFUMES).map(([id, name]) => [name, Number(id)]));

export const MOODS = {
  1: ["Fresh", "상쾌한 날"],
  2: ["Calm", "차분한 날"],
  3: ["Bold", "자신 있는 날"],
  4: ["Sweet", "달콤한 날"],
  5: ["Active", "활기찬 날"],
  6: ["Cozy", "포근한 날"],
  7: ["Mystic", "깊고 신비로운 날"],
  8: ["Random", "무작위"],
};

// main-board/Core/Src/main.c 의 RECIPES[][] 와 같아야 한다 (Lavender, Cedarwood, Vanilla, Bergamot ml)
export const RECIPES = {
  1: [1, 1, 1, 4],
  2: [8, 4, 2, 2],
  3: [2, 6, 2, 4],
  4: [4, 2, 8, 2],
  5: [2, 2, 2, 10],
  6: [4, 4, 8, 2],
  7: [1, 4, 1, 1],
};

export const SCREEN_TEXT = {
  SCREEN_START: "손님을 기다리고 있어요",
  SCREEN_MOODSELECT: "오늘의 기분을 고르는 중",
  SCREEN_CONFIRM: "고른 기분을 확인하는 중",
  SCREEN_BLENDING: "향수를 섞는 중",
  SCREEN_FINISH: "향수가 완성됐어요",
};

/**
 * 보드가 시리얼로 보낸 한 줄을 이벤트로 바꾼다. 관심 없는 줄이면 null.
 *   STATUS : SCREEN_BLENDING / MOOD : 2 / PERFUME : Lavender : 4 / WATER_X : 3 / WATER_O : 3
 */
export function parseLine(line) {
  const parts = line.trim().split(":").map((p) => p.trim());
  if (parts.length < 2 || !parts[1]) return null;
  const key = parts[0].toUpperCase();
  const isNum = (v) => /^\d+$/.test(v);

  if (key === "STATUS") return { kind: "status", screen: parts[1] };
  if (key === "MOOD" && isNum(parts[1])) return { kind: "mood", code: Number(parts[1]) };
  if (key === "PERFUME" && parts.length >= 3 && !Number.isNaN(parseFloat(parts[2])))
    return { kind: "perfume", name: parts[1], ml: parseFloat(parts[2]) };
  if (key === "WATER_X" && isNum(parts[1])) return { kind: "water", sensorId: Number(parts[1]), isLow: true };
  if (key === "WATER_O" && isNum(parts[1])) return { kind: "water", sensorId: Number(parts[1]), isLow: false };
  return null;
}
