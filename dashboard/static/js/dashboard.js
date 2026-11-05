// 대시보드: 1초마다 /sensor/api/state 를 받아 화면을 다시 그린다. (페이지 새로고침 없음)
"use strict";

const OILS = {
  Lavender: "var(--lavender)",
  Cedarwood: "var(--cedarwood)",
  Vanilla: "var(--vanilla)",
  Bergamot: "var(--bergamot)",
};
const MOOD_NAMES = ["Fresh", "Calm", "Bold", "Sweet", "Active", "Cozy", "Mystic", "Random"];
const POLL_MS = 1000;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ml = (v) => (v == null ? "–" : `${Number(v) % 1 ? Number(v).toFixed(1) : Number(v)}ml`);
const clock = (iso) => (iso ? new Date(iso).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }) : "");
const csrf = () => (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";

let state = null;

// ------------------------------------------------------------------ 현재 상태
function renderNow(s) {
  const online = s.device.online;
  $("link").classList.toggle("online", online);
  $("link-text").textContent = online ? "보드 연결됨" : "보드 신호 없음";

  const mood = s.mood;
  $("mood-word").textContent = mood ? mood.name : "아직 고른 기분이 없어요";
  $("mood-label").textContent = mood ? mood.label : "";
  document.querySelector(".mood").classList.toggle("is-empty", !mood);

  const blend = s.current_blend;
  let activity = s.device.screen_text;
  if (!online) {
    activity = "보드와 연결되지 않았어요. 보드의 USB 연결과 수집기 실행을 확인하세요.";
  } else if (blend && blend.active) {
    const doing = blend.steps.find((st) => st.planned_ml && st.injected_ml == null);
    if (doing) activity = `<strong>${esc(doing.perfume)} ${ml(doing.planned_ml)}</strong>를 넣고 있어요`;
  }
  $("activity").innerHTML = online ? activity : esc(activity);
  renderFormula(s);
}

function renderFormula(s) {
  const blend = s.current_blend;
  const choosing = ["SCREEN_MOODSELECT", "SCREEN_CONFIRM"].includes(s.device.screen);
  let rows, title, foot = "";

  if (blend && (blend.active || !choosing)) {
    title = `${blend.mood ?? "알 수 없는 기분"} 레시피`;
    let found = false;
    rows = blend.steps.map((st) => {
      let status = "대기", cls = "";
      if (st.injected_ml != null) { status = "넣음"; cls = "done"; }
      else if (blend.active && !found && st.planned_ml) { status = "넣는 중"; cls = "doing"; found = true; }
      else if (!blend.active) status = "안 넣음";
      return { ...st, status, cls };
    });
    if (blend.active) foot = `${clock(blend.started_at)}에 시작했어요.`;
    else if (blend.completed) foot = `${clock(blend.finished_at)}에 완성, 모두 ${ml(blend.total_ml)}.`;
    else foot = "향료가 부족해 중간에 멈췄어요.";
  } else if (s.mood && s.mood.recipe) {
    title = `${s.mood.name} 레시피`;
    rows = Object.entries(s.mood.recipe).map(([perfume, planned]) => ({ perfume, planned_ml: planned, injected_ml: null, status: "대기", cls: "" }));
    foot = "보드에서 Start 를 누르면 이 순서대로 넣어요.";
  } else {
    title = "레시피";
    rows = Object.keys(OILS).map((perfume) => ({ perfume, planned_ml: null, injected_ml: null, status: "", cls: "" }));
    foot = "기분을 고르면 레시피가 나타나요.";
  }

  $("formula-title").textContent = title;
  $("formula-foot").textContent = foot;
  $("formula-rows").innerHTML = rows.map((r) => `
    <tr>
      <td><span class="oil"><span class="swatch" style="background:${OILS[r.perfume]}"></span>${esc(r.perfume)}</span></td>
      <td class="num">${ml(r.planned_ml)}</td>
      <td class="num">${ml(r.injected_ml)}</td>
      <td><span class="state ${r.cls}">${esc(r.status)}</span></td>
    </tr>`).join("");
}

// ------------------------------------------------------------------ 향료 통
function renderVials(s) {
  const tanks = s.mock ? Object.fromEntries(s.mock.tanks.map((t) => [t.name, t])) : null;
  $("organ-hint").textContent = tanks
    ? "가상 향료 통의 실제 잔량이에요. 점선이 수위 센서 위치예요."
    : "수위 센서가 잔량 부족을 감지하면 빨간색으로 표시돼요.";

  // 통은 처음 한 번만 만들고 이후에는 값만 바꾼다 → 액체 높이가 부드럽게 줄어듦
  const list = $("vials");
  if (list.children.length !== s.stock.length || list.dataset.mock !== String(!!tanks)) {
    list.dataset.mock = String(!!tanks);
    list.innerHTML = s.stock.map((st) => `
      <li class="vial" data-name="${esc(st.name)}">
        <div class="tube" style="--oil:${OILS[st.name]}">
          <div class="liquid"></div>
          <div class="low-mark"></div>
        </div>
        <div class="vial-meta">
          <p class="vial-name">${esc(st.name)}</p>
          <p class="vial-state"></p>
          ${tanks ? `<button type="button" class="text-btn" data-drain="${st.id}">비우기</button>` : ""}
        </div>
      </li>`).join("");
  }

  s.stock.forEach((st, i) => {
    const li = list.children[i];
    const tank = tanks && tanks[st.name];
    let level, low;
    if (tank) {
      level = (tank.ml / tank.capacity) * 100;
      low = (tank.low_level / tank.capacity) * 100;
    } else {
      level = st.is_low ? 10 : 88; // 실제 보드는 '부족/충분'만 알 수 있음
      low = 16;
    }
    li.className = `vial ${st.is_low == null ? "is-unknown" : st.is_low ? "is-low" : ""}`;
    li.querySelector(".tube").style.setProperty("--low", `${low}%`);
    li.querySelector(".liquid").style.setProperty("--level", `${level}%`);
    li.querySelector(".vial-state").textContent = st.is_low == null ? "센서 값 없음"
      : st.is_low ? `부족${st.since ? `, ${clock(st.since)}부터` : ""}`
      : tank ? `${ml(tank.ml)} 남음` : "충분";
  });
}

// ------------------------------------------------------------------ 제조 기록
function renderLog(s) {
  $("today").textContent = s.today_count ? `오늘 ${s.today_count}병 완성` : "";
  if (!s.recent_blends.length) {
    $("blends").innerHTML = `<li class="empty">${s.mock
      ? "아직 만든 향수가 없어요. 오른쪽 LCD 화면을 눌러 첫 향수를 만들어 보세요."
      : "아직 만든 향수가 없어요. 보드에서 기분을 고르면 여기에 기록돼요."}</li>`;
    return;
  }
  $("blends").innerHTML = s.recent_blends.map((b) => {
    const total = b.steps.reduce((sum, st) => sum + (st.injected_ml || 0), 0) || 1;
    const mix = b.steps.filter((st) => st.injected_ml)
      .map((st) => `<i style="width:${(st.injected_ml / total) * 100}%;background:${OILS[st.perfume]}" title="${esc(st.perfume)} ${ml(st.injected_ml)}"></i>`).join("");
    return `
      <li class="blend ${b.completed ? "" : "aborted"}">
        <time datetime="${b.started_at}">${clock(b.started_at)}</time>
        <p class="blend-mood">${esc(b.mood ?? "?")}<span>${b.completed ? esc(b.mood_label) : "향료가 부족해 만들지 못함"}</span></p>
        <p class="blend-ml">${ml(b.total_ml)}</p>
        <div class="mix" aria-hidden="true">${mix}</div>
      </li>`;
  }).join("");
}

// ------------------------------------------------------------------ 가상 LCD (mock)
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

let lcdSignature = "";
function renderDevice(s) {
  const mock = s.mock;
  $("device").hidden = !mock;
  if (!mock) return;

  $("auto").checked = mock.auto;
  $("speed").textContent = `실제 보드보다 ${mock.speed}배 빠르게 움직여요.`;

  const sig = JSON.stringify(mock.lcd);
  if (sig === lcdSignature) return; // 화면이 바뀔 때만 다시 그림
  lcdSignature = sig;

  $("lcd").innerHTML = mock.lcd.cells.map((c) => {
    const key = lcdKey(mock.screen, c.text);
    const pos = `left:${(c.x / 128) * 100}%;top:${(c.y / 128) * 100}%`;
    return key
      ? `<button type="button" class="cell key" style="${pos}" data-key="${key.key}" data-mood="${key.mood ?? ""}" aria-label="${esc(key.label)}">${esc(c.text)}</button>`
      : `<span class="cell" style="${pos}">${esc(c.text)}</span>`;
  }).join("");
  $("lcd").dataset.screen = mock.screen;
  $("lcd").title = ["SCREEN_START", "SCREEN_FINISH"].includes(mock.screen) ? "화면을 눌러 다음으로" : "";
}

async function mockPost(path, body) {
  const res = await fetch(`/sensor/api/mock/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!data.ok) alert(data.message);
  setTimeout(poll, 150);
}

$("lcd").addEventListener("click", (e) => {
  const lcd = $("lcd");
  lcd.classList.add("pressed");
  setTimeout(() => lcd.classList.remove("pressed"), 120);

  const btn = e.target.closest("[data-key]");
  if (btn) return mockPost("press", { key: btn.dataset.key, mood: Number(btn.dataset.mood) || null });
  // 빈 곳 터치는 START / FINISH 화면에서만 의미가 있다 (다른 화면에서는 실제 기기처럼 무시)
  if (["SCREEN_START", "SCREEN_FINISH"].includes(lcd.dataset.screen)) mockPost("press", { key: "tap" });
});
$("auto").addEventListener("change", (e) => mockPost("auto", { on: e.target.checked }));
$("refill").addEventListener("click", () => mockPost("tank", { action: "refill" }));
$("vials").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-drain]");
  if (btn) mockPost("tank", { action: "drain", id: Number(btn.dataset.drain) });
});

// ------------------------------------------------------------------ 폴링
let timer = null;
async function poll() {
  clearTimeout(timer);
  try {
    const res = await fetch("/sensor/api/state", { cache: "no-store" });
    state = await res.json();
    renderNow(state);
    renderVials(state);
    renderLog(state);
    renderDevice(state);
  } catch (err) {
    $("link").classList.remove("online");
    $("link-text").textContent = "대시보드 서버에 연결할 수 없어요";
  }
  timer = setTimeout(poll, POLL_MS);
}
poll();
