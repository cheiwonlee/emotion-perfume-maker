// 가상 터치 LCD — 화면 오른쪽의 접이식 사이드 패널.
// 실제 기기에서 메인보드와 따로 떨어져 있는 LCD 판을 흉내 낸다.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const MOOD_NAMES = ["Fresh", "Calm", "Bold", "Sweet", "Active", "Cozy", "Mystic", "Random"];

// 화면마다 무엇을 누르면 되는지 알려 주는 한 줄
const TIPS = {
  SCREEN_START: "화면 아무 곳이나 누르면 기분 선택으로 넘어가요.",
  SCREEN_MOODSELECT: "오늘의 기분을 눌러 고르세요.",
  SCREEN_CONFIRM: "[Start] 로 제조를 시작하고, [Back] 으로 돌아가요.",
  SCREEN_BLENDING: "만드는 동안에는 터치가 무시돼요.",
  SCREEN_FINISH: "화면을 누르면 처음 화면으로 돌아가요.",
};

let signature = "";

// ------------------------------------------------------------------ 화면 그리기
function lcdKey(screen, text) {
  if (screen === "SCREEN_MOODSELECT") {
    const i = MOOD_NAMES.indexOf(text.trim());
    if (i >= 0) return { key: "mood", mood: i + 1, label: `${text} 선택` };
  }
  if (screen === "SCREEN_CONFIRM") {
    if (text.includes("[Back]")) return { key: "back", label: "뒤로" };
    if (text.includes("[Start]")) return { key: "start", label: "제조 시작" };
  }
  return null;
}

/** 가상 보드 상태(mock)로 LCD 화면을 그린다. 화면이 바뀔 때만 다시 그림 */
export function drawLcd(mock) {
  const sig = JSON.stringify([mock.screen, mock.lcd]);
  if (sig === signature) return;
  signature = sig;
  const lcd = $("lcd");
  lcd.dataset.screen = mock.screen;
  lcd.classList.toggle("tappable", ["SCREEN_START", "SCREEN_FINISH"].includes(mock.screen));
  $("lcd-tip").textContent = mock.lcd.title === "MESSAGE" ? "잠시 후 처음 화면으로 돌아가요." : TIPS[mock.screen] ?? "";
  lcd.innerHTML = mock.lcd.cells.map((c) => {
    const key = lcdKey(mock.screen, c.text);
    const pos = `left:${(c.x / 128) * 100}%;top:${(c.y / 128) * 100}%`;
    return key
      ? `<button type="button" class="cell key" style="${pos}" data-key="${key.key}" data-mood="${key.mood ?? ""}" aria-label="${esc(key.label)}">${esc(c.text)}</button>`
      : `<span class="cell" style="${pos}">${esc(c.text)}</span>`;
  }).join("");
}

export function resetLcd() {
  signature = "";
  $("lcd").innerHTML = "";
  $("lcd-tip").textContent = "";
}

// ------------------------------------------------------------------ 패널 보이기·접기
/** 가상 보드가 있는 모드에서만 패널 자체를 보여 준다 */
export function setLcdAvailable(available) {
  $("lcd-panel").hidden = !available;
  $("layout").classList.toggle("has-lcd", available && isLcdOpen());
}

export function setLcdOpen(open) {
  $("lcd-panel").dataset.open = String(open);
  $("lcd-toggle").setAttribute("aria-expanded", String(open));
  $("lcd-toggle").setAttribute("aria-label", open ? "터치 LCD 패널 접기" : "터치 LCD 패널 펼치기");
  $("layout").classList.toggle("has-lcd", open && !$("lcd-panel").hidden);
}

export const isLcdOpen = () => $("lcd-panel").dataset.open === "true";

/** 터치를 보낼 곳 연결 (한 번만 호출) */
export function setupLcdPanel(onPress, onToggle) {
  $("lcd").addEventListener("click", (e) => {
    const lcd = $("lcd");
    lcd.classList.add("pressed");
    setTimeout(() => lcd.classList.remove("pressed"), 120);
    const btn = e.target.closest("[data-key]");
    if (btn) return onPress(btn.dataset.key, Number(btn.dataset.mood) || null);
    // 빈 곳 터치는 START / FINISH 화면에서만 의미가 있다 (실제 기기처럼 다른 화면에서는 무시)
    if (lcd.classList.contains("tappable")) onPress("tap");
  });
  $("lcd-toggle").addEventListener("click", () => onToggle(!isLcdOpen()));
}
