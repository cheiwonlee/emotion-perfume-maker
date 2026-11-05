// 시작점: 접속하면 모드를 고르고, 고른 소스를 화면에 연결한다.
//   ?mode=virtual | serial | server  로 바로 들어갈 수도 있다. (python run.py는 ?mode=server로 연다)
import { bindControls, render, renderUnreachable, resetView, setOfflineHint } from "./render.js";
import { SerialSource, ServerSource, VirtualSource } from "./sources.js";

const $ = (id) => document.getElementById(id);
const LAST_MODE_KEY = "perfume-maker:last-mode";

// Django가 이 페이지를 내려줄 때만 <meta name="api-base">가 들어 있다 → 로컬 서버 모드 가능
const apiBase = document.querySelector('meta[name="api-base"]')?.content ?? null;

const MODES = {
  virtual: {
    label: "가상 보드",
    available: () => true,
    create: () => new VirtualSource(),
    offline: "가상 보드를 준비하는 중이에요.",
  },
  serial: {
    label: "실제 보드 (USB)",
    available: () => (SerialSource.supported() ? true
      : "이 브라우저는 USB 시리얼(Web Serial)을 지원하지 않아요. 데스크톱 Chrome이나 Edge에서 열어 주세요."),
    create: () => new SerialSource(),
    offline: "보드가 연결되지 않았어요. 위쪽의 ‘USB로 연결’을 눌러 메인보드 포트를 고르세요.",
  },
  server: {
    label: "로컬 서버",
    available: () => (apiBase ? true
      : "이 모드는 내 컴퓨터에서 python run.py로 연 페이지에서만 쓸 수 있어요."),
    create: () => new ServerSource(apiBase),
    offline: "보드 신호가 없어요. run.py를 --real로 실행했다면 보드 USB 연결을 확인하세요.",
  },
};

// 지금 쓰는 소스. 화면의 버튼들은 항상 이 객체를 거쳐 현재 소스로 전달된다.
let source = null;
let mode = null;
const proxy = {
  press: (...a) => source?.press?.(...a),
  tank: (...a) => source?.tank?.(...a),
  setAuto: (...a) => source?.setAuto?.(...a),
};
bindControls(proxy);

function setUrlMode(value) {
  const url = new URL(location.href);
  if (value) url.searchParams.set("mode", value); else url.searchParams.delete("mode");
  history.replaceState(null, "", url);
}

// ------------------------------------------------------------------ 모드 고르기 화면
function showChooser() {
  source?.stop();
  source = null; mode = null;
  setUrlMode(null);
  $("dashboard").hidden = true;
  $("mode-btn").hidden = true;
  $("mode-label").hidden = true;
  $("serial-btn").hidden = true;
  $("link").hidden = true;
  $("chooser").hidden = false;

  const last = localStorage.getItem(LAST_MODE_KEY);
  document.querySelectorAll(".mode").forEach((btn) => {
    const ok = MODES[btn.dataset.mode].available();
    btn.disabled = ok !== true;
    btn.querySelector(".mode-note").textContent = ok !== true ? ok : btn.dataset.mode === last ? "지난번에 고른 모드" : "";
  });
}

document.querySelectorAll(".mode").forEach((btn) =>
  btn.addEventListener("click", () => start(btn.dataset.mode, { userClick: true })));
$("mode-btn").addEventListener("click", showChooser);

// ------------------------------------------------------------------ 모드 시작
async function start(nextMode, { userClick = false } = {}) {
  const def = MODES[nextMode];
  if (!def || def.available() !== true) return showChooser();

  source?.stop();
  resetView();
  mode = nextMode;
  localStorage.setItem(LAST_MODE_KEY, mode);
  setUrlMode(mode);

  $("chooser").hidden = true;
  $("dashboard").hidden = false;
  $("link").hidden = false;
  $("mode-btn").hidden = false;
  $("mode-label").hidden = false;
  $("mode-label").textContent = def.label;
  setOfflineHint(def.offline);

  source = def.create();
  source.start((state) => {
    if (state) render(state);
    else renderUnreachable("서버에 연결할 수 없어요. run.py가 켜져 있는지 확인하세요.");
    if (mode === "serial") updateSerialButton(state);
  });

  if (mode === "serial") {
    await source.reconnect();                 // 예전에 허락한 포트면 바로 연결
    if (!source.connected() && userClick) source.choose(); // 방금 클릭했으면 포트 고르기 창
  }
}

// ------------------------------------------------------------------ USB 연결 버튼 (실제 보드 모드)
function updateSerialButton(state) {
  const btn = $("serial-btn");
  btn.hidden = false;
  btn.textContent = state?.serial?.connected ? "연결 끊기" : "USB로 연결";
  if (state?.serial?.error) setOfflineHint(state.serial.error);
}
$("serial-btn").addEventListener("click", () => {
  if (!(source instanceof SerialSource)) return;
  if (source.connected()) source.disconnect();
  else source.choose();
});

// ------------------------------------------------------------------ 처음 열 때
const requested = new URLSearchParams(location.search).get("mode");
if (requested && MODES[requested]?.available() === true) start(requested);
else showChooser();
