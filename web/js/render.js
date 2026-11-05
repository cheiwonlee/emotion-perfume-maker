// 대시보드 화면 그리기. 상태(state)는 sources.js의 어느 소스에서 오든 같은 모양이다.
//   위: 지금 상태(단계·진행률)   아래: 향료 통 / 제조 기록

const OILS = {
  Lavender: "var(--lavender)",
  Cedarwood: "var(--cedarwood)",
  Vanilla: "var(--vanilla)",
  Bergamot: "var(--bergamot)",
};
const STAGES = ["SCREEN_START", "SCREEN_MOODSELECT", "SCREEN_CONFIRM", "SCREEN_BLENDING", "SCREEN_FINISH"];

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ml = (v) => (v == null ? "–" : `${Number(v) % 1 ? Number(v).toFixed(1) : Number(v)}ml`);
const num = (v) => (Number(v) % 1 ? Number(v).toFixed(1) : String(Number(v)));
const clock = (iso) => (iso ? new Date(iso).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }) : "");
const seconds = (from, to) => Math.max(0, Math.round(((to ? Date.parse(to) : Date.now()) - Date.parse(from)) / 1000));
const duration = (sec) => (sec < 60 ? `${sec}초` : `${Math.floor(sec / 60)}분 ${sec % 60}초`);

// 연결이 끊겼을 때 보여 줄 안내 (모드마다 다름) — app.js가 정한다
let offlineHint = "보드와 연결되지 않았어요.";
export function setOfflineHint(text) { offlineHint = text; }

// ------------------------------------------------------------------ 지금 상태 판단
function lowTanks(s) {
  return s.mock ? s.mock.tanks.filter((t) => t.is_low).map((t) => t.name)
    : s.stock.filter((st) => st.is_low).map((st) => st.name);
}

/** 화면에 보여 줄 '지금 상태' 하나로 정리 */
function describe(s) {
  const screen = s.device.screen;
  const blend = s.current_blend;
  const mood = s.mood;
  const low = lowTanks(s);

  if (!s.device.online) {
    return { tone: "off", chip: "연결 끊김", headline: "보드 신호가 없어요", sub: offlineHint };
  }
  if (screen === "SCREEN_BLENDING" && blend?.active) {
    const steps = blend.steps.filter((st) => st.planned_ml);
    const doneCount = steps.filter((st) => st.injected_ml != null).length;
    const doing = steps.find((st) => st.injected_ml == null);
    return {
      tone: "busy", chip: "주입 중",
      headline: `${blend.mood ?? "향수"} 향수를 만드는 중`,
      sub: doing
        ? `<strong>${esc(doing.perfume)} ${ml(doing.planned_ml)}</strong> 넣는 중 (${doneCount + 1}/${steps.length}번째), 시작한 지 ${duration(seconds(blend.started_at))}`
        : "마무리하는 중",
      blend,
    };
  }
  if (screen === "SCREEN_FINISH" && blend?.completed) {
    return {
      tone: "done", chip: "완료",
      headline: `${blend.mood} 향수 완성`,
      sub: `모두 ${ml(blend.total_ml)}, ${duration(seconds(blend.started_at, blend.finished_at))} 걸렸어요. LCD를 누르면 처음 화면으로 돌아가요.`,
      blend,
    };
  }
  if (low.length) {
    return {
      tone: "alert", chip: "재고 부족",
      headline: `${low.join(", ")} 통이 부족해요`,
      sub: "통을 채운 뒤 LCD를 눌러 처음부터 다시 시작하세요.",
      blend: blend && !blend.active && !blend.completed ? blend : null,
    };
  }
  if (screen === "SCREEN_CONFIRM" && mood) {
    const total = Object.values(mood.recipe ?? {}).reduce((a, v) => a + v, 0);
    return {
      tone: "idle", chip: "확인",
      headline: `${mood.name} 향수를 만들까요?`,
      sub: `${esc(mood.label)}, 향료 ${ml(total)}. LCD에서 Start를 누르면 시작해요.`,
      preview: mood,
    };
  }
  if (screen === "SCREEN_MOODSELECT") {
    return { tone: "idle", chip: "기분 선택", headline: "기분을 고르는 중", sub: "LCD에서 오늘의 기분을 눌러 주세요." };
  }
  const last = s.recent_blends[0];
  return {
    tone: "idle", chip: "대기",
    headline: "손님을 기다리고 있어요",
    sub: !last ? "LCD를 누르면 기분을 고를 수 있어요."
      : last.completed ? `직전 향수: ${esc(last.mood)} ${ml(last.total_ml)} (${clock(last.finished_at)} 완성)`
      : `직전 제조: ${esc(last.mood)}, 중간에 멈춤 (${clock(last.started_at)})`,
  };
}

// ------------------------------------------------------------------ 위: 지금 상태
function renderStatus(s) {
  const online = s.device.online;
  $("link").classList.toggle("online", online);
  $("link-text").textContent = online ? "보드 연결됨" : "보드 신호 없음";

  const d = describe(s);
  $("status").dataset.tone = d.tone;
  $("chip-text").textContent = d.chip;
  $("headline").textContent = d.headline;
  $("subline").innerHTML = d.sub ?? "";

  // 단계 표시: 지금 단계까지 채움
  const current = online ? STAGES.indexOf(s.device.screen) : -1;
  [...$("stages").children].forEach((li, i) => {
    li.className = i < current ? "past" : i === current ? "current" : "";
    if (i === current) li.setAttribute("aria-current", "step"); else li.removeAttribute("aria-current");
  });

  // 진행 막대: 제조 중·완료·중단이면 실제 값, 확인 단계면 레시피 미리 보기
  let steps = null;
  let active = false;
  if (d.blend) { steps = d.blend.steps; active = d.blend.active; }
  else if (d.preview?.recipe) steps = Object.entries(d.preview.recipe).map(([perfume, planned_ml]) => ({ perfume, planned_ml, injected_ml: null }));
  renderProgress(steps, active, Boolean(d.preview));
}

function renderProgress(steps, active, preview) {
  const show = Boolean(steps?.some((st) => st.planned_ml));
  $("progress").hidden = $("legend").hidden = $("percent").hidden = !show;
  if (!show) return;

  const planned = steps.filter((st) => st.planned_ml);
  const total = planned.reduce((a, st) => a + st.planned_ml, 0);
  const done = planned.reduce((a, st) => a + (st.injected_ml ?? 0), 0);
  const pct = Math.round((done / total) * 100);
  $("percent-num").textContent = preview ? "0" : String(pct);
  $("progress").setAttribute("aria-valuenow", String(pct));
  $("progress").setAttribute("aria-valuetext", `${num(done)}ml / ${num(total)}ml`);

  const doingIndex = active ? planned.findIndex((st) => st.injected_ml == null) : -1;
  $("progress").innerHTML = planned.map((st, i) => {
    const state = st.injected_ml != null ? "done" : i === doingIndex ? "doing" : "todo";
    return `<span class="seg ${state}" style="flex:${st.planned_ml};--oil:${OILS[st.perfume]}"><i></i></span>`;
  }).join("");

  $("legend").innerHTML = planned.map((st, i) => {
    const state = st.injected_ml != null ? "넣음" : i === doingIndex ? "넣는 중" : active || preview ? "대기" : "못 넣음";
    const cls = st.injected_ml != null ? "done" : i === doingIndex ? "doing" : "";
    return `
      <li class="${cls}">
        <span class="legend-name"><span class="swatch" style="background:${OILS[st.perfume]}"></span>${esc(st.perfume)}</span>
        <span class="legend-ml">${num(st.injected_ml ?? 0)} / ${ml(st.planned_ml)} <span class="legend-state">${state}</span></span>
      </li>`;
  }).join("");
}

// ------------------------------------------------------------------ 향료 통
function renderVials(s) {
  const tanks = s.mock ? Object.fromEntries(s.mock.tanks.map((t) => [t.name, t])) : null;
  $("organ-hint").textContent = tanks
    ? "가상 향료 통의 실제 잔량이에요. 점선이 수위 센서 위치예요."
    : "수위 센서가 잔량 부족을 감지하면 빨간색으로 표시돼요.";
  $("sim-controls").hidden = !tanks;

  // 통은 처음 한 번만 만들고 이후에는 값만 바꾼다 → 액체 높이가 부드럽게 줄어듦
  const list = $("vials");
  if (list.children.length !== s.stock.length || list.dataset.mock !== String(!!tanks)) {
    list.dataset.mock = String(!!tanks);
    list.innerHTML = s.stock.map((st) => `
      <li class="vial">
        <div class="tube" style="--oil:${OILS[st.name]}">
          <div class="liquid"></div>
          <div class="low-mark"></div>
        </div>
        <p class="vial-name">${esc(st.name)}</p>
        <p class="vial-state"></p>
        ${tanks ? `<button type="button" class="btn btn-secondary btn-xs" data-drain="${st.id}" aria-label="${esc(st.name)} 통 비우기">비우기</button>` : ""}
      </li>`).join("");
  }

  s.stock.forEach((st, i) => {
    const li = list.children[i];
    const tank = tanks && tanks[st.name];
    const level = tank ? (tank.ml / tank.capacity) * 100 : st.is_low ? 10 : 88; // 실제 보드는 부족/충분만 앎
    const low = tank ? (tank.low_level / tank.capacity) * 100 : 16;
    const isLow = tank ? tank.is_low : st.is_low;
    li.className = `vial ${isLow == null ? "is-unknown" : isLow ? "is-low" : ""}`;
    li.querySelector(".tube").style.setProperty("--low", `${low}%`);
    li.querySelector(".liquid").style.setProperty("--level", `${level}%`);
    li.querySelector(".vial-state").textContent = tank
      ? `${isLow ? "부족 " : ""}${ml(tank.ml)}`
      : isLow == null ? "센서 값 없음" : isLow ? "부족" : "충분";
  });
}

// ------------------------------------------------------------------ 제조 기록
function renderLog(s) {
  $("today").textContent = s.today_count ? `오늘 ${s.today_count}병 완성` : "";
  if (!s.recent_blends.length) {
    $("blends").innerHTML = `<li class="empty">${s.mock
      ? "아직 만든 향수가 없어요. 오른쪽 터치 LCD를 눌러 첫 향수를 만들어 보세요."
      : "아직 만든 향수가 없어요. 보드에서 기분을 고르면 여기에 기록돼요."}</li>`;
    return;
  }
  $("blends").innerHTML = s.recent_blends.slice(0, 5).map((b) => {
    const total = b.steps.reduce((sum, st) => sum + (st.injected_ml || 0), 0) || 1;
    const mix = b.steps.filter((st) => st.injected_ml)
      .map((st) => `<i style="width:${(st.injected_ml / total) * 100}%;background:${OILS[st.perfume]}" title="${esc(st.perfume)} ${ml(st.injected_ml)}"></i>`).join("");
    return `
      <li class="blend ${b.completed ? "" : "aborted"}">
        <time datetime="${b.started_at}">${clock(b.started_at)}</time>
        <p class="blend-mood">${esc(b.mood ?? "?")}<span>${b.completed ? esc(b.mood_label) : "만들다 멈춤"}</span></p>
        <p class="blend-ml">${ml(b.total_ml)}</p>
        <div class="mix" aria-hidden="true">${mix}</div>
      </li>`;
  }).join("");
}

// ------------------------------------------------------------------ 진입점
let autoHoldUntil = 0;

export function render(state) {
  renderStatus(state);
  renderVials(state);
  renderLog(state);
  if (state.mock && Date.now() > autoHoldUntil) $("auto").checked = state.mock.auto;
}

export function renderUnreachable(text) {
  $("link").classList.remove("online");
  $("link-text").textContent = text;
}

/** 향료 통·자동 시연 버튼을 소스의 동작에 연결 (LCD 창은 lcd-view.js) */
export function bindControls(source) {
  $("auto").addEventListener("change", (e) => {
    autoHoldUntil = Date.now() + 2000; // 서버가 반영할 때까지 폴링이 예전 값으로 되돌리지 않게
    source.setAuto(e.target.checked);
  });
  $("refill").addEventListener("click", () => source.tank("refill"));
  $("vials").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-drain]");
    if (btn) source.tank("drain", Number(btn.dataset.drain));
  });
}

/** 모드가 바뀌면 화면 상태 초기화 */
export function resetView() {
  $("vials").innerHTML = "";
}
