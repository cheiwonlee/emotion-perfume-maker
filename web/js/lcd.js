// 가상 터치 LCD 탭. 실제 기기에서 메인보드와 따로 떨어진 LCD 판을 흉내 낸다.
//   ?source=virtual : 대시보드 탭에서 도는 가상 보드와 BroadcastChannel 로 연결
//   ?source=server&api=/sensor/ : python run.py 의 가상 보드와 서버 API 로 연결
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const MOOD_NAMES = ["Fresh", "Calm", "Bold", "Sweet", "Active", "Cozy", "Mystic", "Random"];
const STALE_MS = 2500;

const params = new URLSearchParams(location.search);
const source = params.get("source") === "server" ? "server" : "virtual";
const api = (params.get("api") || "/sensor/").replace(/\/$/, "");

let lastSeen = 0;
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

function draw(mock) {
  lastSeen = Date.now();
  const sig = JSON.stringify([mock.screen, mock.lcd]);
  if (sig === signature) return; // 화면이 바뀔 때만 다시 그림
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

function updateLink() {
  const alive = Date.now() - lastSeen < STALE_MS;
  $("lcd-status").classList.toggle("online", alive);
  $("lcd-status-text").textContent = alive ? "메인보드와 연결됨"
    : source === "virtual" ? "대시보드 탭을 가상 보드 모드로 열어 두세요" : "서버에 연결할 수 없어요. run.py가 켜져 있는지 확인하세요";
  if (!alive) { signature = ""; $("lcd").innerHTML = ""; }
}
setInterval(updateLink, 500);

// ------------------------------------------------------------------ 연결
let press;
if (source === "virtual") {
  const channel = new BroadcastChannel("perfume-maker");
  channel.onmessage = (e) => { if (e.data?.type === "mock") draw(e.data.mock); };
  channel.postMessage({ type: "hello" }); // 대시보드에게 지금 화면을 바로 보내 달라고 요청
  press = (key, mood) => channel.postMessage({ type: "press", key, mood });
} else {
  const poll = async () => {
    try {
      const state = await (await fetch(`${api}/api/state`, { cache: "no-store" })).json();
      if (state.mock) draw(state.mock);
    } catch { /* 서버 꺼짐 → updateLink 가 표시 */ }
    setTimeout(poll, 500);
  };
  poll();
  const csrf = () => (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
  press = (key, mood) => fetch(`${api}/api/mock/press`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
    body: JSON.stringify({ key, mood }),
  });
}

// ------------------------------------------------------------------ 터치
$("lcd").addEventListener("click", (e) => {
  const lcd = $("lcd");
  lcd.classList.add("pressed");
  setTimeout(() => lcd.classList.remove("pressed"), 120);
  const btn = e.target.closest("[data-key]");
  if (btn) return press(btn.dataset.key, Number(btn.dataset.mood) || null);
  // 빈 곳 터치는 START / FINISH 화면에서만 의미가 있다 (실제 기기처럼 다른 화면에서는 무시)
  if (["SCREEN_START", "SCREEN_FINISH"].includes(lcd.dataset.screen)) press("tap");
});
