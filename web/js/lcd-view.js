// 가상 터치 LCD 창. 대시보드 위에 떠 있는 작은 창으로, 마우스(또는 터치)로 끌어서 옮길 수 있다.
// 실제 기기에서 메인보드와 떨어져 있는 LCD 판을 흉내 낸다.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const MOOD_NAMES = ["Fresh", "Calm", "Bold", "Sweet", "Active", "Cozy", "Mystic", "Random"];
const POS_KEY = "perfume-maker:lcd-window";
const MARGIN = 8;

let press = () => {};
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
  lcd.title = ["SCREEN_START", "SCREEN_FINISH"].includes(mock.screen) ? "화면을 눌러 다음으로" : "";
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
}

// ------------------------------------------------------------------ 창 열기·닫기·위치
const win = () => $("lcd-window");

function clamp(x, y) {
  const w = win();
  const maxX = window.innerWidth - w.offsetWidth - MARGIN;
  const maxY = window.innerHeight - w.offsetHeight - MARGIN;
  return [Math.min(Math.max(MARGIN, x), Math.max(MARGIN, maxX)), Math.min(Math.max(MARGIN, y), Math.max(MARGIN, maxY))];
}

function place(x, y, save = false) {
  [x, y] = clamp(x, y);
  win().style.left = `${x}px`;
  win().style.top = `${y}px`;
  if (save) try { localStorage.setItem(POS_KEY, JSON.stringify({ x, y })); } catch { /* 무시 */ }
}

function defaultPlace() {
  // 처음에는 오른쪽 아래 (대시보드 위쪽 상태 패널을 가리지 않게)
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(POS_KEY)); } catch { /* 무시 */ }
  if (saved) place(saved.x, saved.y);
  else place(window.innerWidth - win().offsetWidth - 24, window.innerHeight - win().offsetHeight - 24);
}

export function setLcdOpen(open) {
  const w = win();
  const wasHidden = w.hidden;
  w.hidden = !open;
  $("lcd-toggle").setAttribute("aria-pressed", String(open));
  $("lcd-toggle").textContent = open ? "가상 LCD 닫기" : "가상 LCD 열기";
  if (open && wasHidden) defaultPlace();
}

export const isLcdOpen = () => !win().hidden;

/** 터치를 보낼 곳 연결 + 끌기 설정 (한 번만 호출) */
export function setupLcdWindow(onPress) {
  press = onPress;

  // 터치
  $("lcd").addEventListener("click", (e) => {
    const lcd = $("lcd");
    lcd.classList.add("pressed");
    setTimeout(() => lcd.classList.remove("pressed"), 120);
    const btn = e.target.closest("[data-key]");
    if (btn) return press(btn.dataset.key, Number(btn.dataset.mood) || null);
    // 빈 곳 터치는 START / FINISH 화면에서만 의미가 있다 (실제 기기처럼 다른 화면에서는 무시)
    if (["SCREEN_START", "SCREEN_FINISH"].includes(lcd.dataset.screen)) press("tap");
  });

  // 끌어서 옮기기: 제목 막대를 잡고 드래그 (마우스·터치 모두)
  const bar = $("lcd-bar");
  let drag = null;
  bar.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || e.target.closest("button")) return;
    const r = win().getBoundingClientRect();
    drag = { dx: e.clientX - r.left, dy: e.clientY - r.top };
    bar.setPointerCapture(e.pointerId);
    win().classList.add("dragging");
  });
  bar.addEventListener("pointermove", (e) => {
    if (drag) place(e.clientX - drag.dx, e.clientY - drag.dy);
  });
  const end = (e) => {
    if (!drag) return;
    drag = null;
    win().classList.remove("dragging");
    const r = win().getBoundingClientRect();
    place(r.left, r.top, true);
    if (bar.hasPointerCapture(e.pointerId)) bar.releasePointerCapture(e.pointerId);
  };
  bar.addEventListener("pointerup", end);
  bar.addEventListener("pointercancel", end);

  // 키보드로도 옮기기: 제목 막대에 초점을 두고 방향키 (Shift 를 누르면 크게)
  bar.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 40 : 10;
    const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    if (!d) return;
    e.preventDefault();
    const r = win().getBoundingClientRect();
    place(r.left + d[0], r.top + d[1], true);
  });

  $("lcd-close").addEventListener("click", () => setLcdOpen(false));
  window.addEventListener("resize", () => {
    if (isLcdOpen()) { const r = win().getBoundingClientRect(); place(r.left, r.top); }
  });
}
