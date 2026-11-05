// 대시보드가 상태를 받아 오는 세 가지 방법. 모두 같은 모양의 상태(Django /sensor/api/state와 동일)를 넘겨준다.
//   VirtualSource : 브라우저 안의 가상 보드
//   SerialSource  : USB로 연결한 실제 메인보드 (Web Serial — Chrome/Edge)
//   ServerSource  : python run.py로 띄운 Django 서버
import { parseLine } from "./protocol.js";
import { Store } from "./store.js";
import { VirtualBoard } from "./virtual-board.js";

const TICK_MS = 500;

// ---------------------------------------------------------------- 공통: 시리얼 줄 → Store → 화면
class LocalSource {
  constructor(persistKey) {
    this.store = new Store(persistKey);
    this.onState = () => {};
    this.timer = null;
  }
  start(onState) {
    this.onState = onState;
    this.timer = setInterval(() => this.tick(), TICK_MS);
    this.tick();
  }
  stop() { clearInterval(this.timer); }
  feed(line) {
    const event = parseLine(line);
    if (event) { this.store.handle(event); this.emit(); }
  }
  tick() { this.store.heartbeat(this.connected()); this.emit(); }
  emit() { this.onState(this.state()); }
  state() { return this.store.snapshot(); }
  clearHistory() { this.store.clearHistory(); this.emit(); }
}

// ---------------------------------------------------------------- 가상 보드
export class VirtualSource extends LocalSource {
  constructor({ speed = 5 } = {}) {
    super("perfume-maker:virtual");
    this.board = new VirtualBoard((line) => this.feed(line), { speed });
    // 별도 탭의 가상 LCD(lcd.html)와 연결: 화면을 보내 주고, 터치를 받는다
    this.channel = new BroadcastChannel("perfume-maker");
    this.channel.onmessage = (e) => {
      if (e.data?.type === "press") this.press(e.data.key, e.data.mood);
      if (e.data?.type === "hello") this.emit();
    };
  }
  connected() { return true; }
  state() { return { ...super.state(), mock: this.board.snapshot() }; }
  emit() {
    const state = this.state();
    this.onState(state);
    this.channel.postMessage({ type: "mock", mock: state.mock });
  }
  stop() { super.stop(); this.board.stop(); this.channel.close(); }
  press(key, mood) { this.board.press(key, mood); setTimeout(() => this.emit(), 120); }
  tank(action, id) { this.board.tank(action, id); this.emit(); }
  setAuto(on) { this.board.setAuto(on); this.emit(); }
}

// ---------------------------------------------------------------- 실제 보드 (Web Serial)
export class SerialSource extends LocalSource {
  static supported() { return "serial" in navigator; }

  constructor() {
    super("perfume-maker:serial");
    this.port = null;
    this.reader = null;
    this.portLabel = "";
    this.error = "";
  }
  connected() { return Boolean(this.port); }
  state() {
    return { ...super.state(), serial: { connected: this.connected(), label: this.portLabel, error: this.error } };
  }

  /** 이전에 허용한 포트가 있으면 사용자 클릭 없이 다시 연결 */
  async reconnect() {
    const [port] = await navigator.serial.getPorts();
    if (port) await this.open(port);
  }

  /** 포트 고르기 창 띄우기 (버튼 클릭 안에서 불러야 함) */
  async choose() {
    try {
      const port = await navigator.serial.requestPort();
      await this.open(port);
    } catch (e) {
      if (e.name !== "NotFoundError") this.error = `연결하지 못했어요: ${e.message}`; // NotFoundError = 창을 닫음
      this.emit();
    }
  }

  async open(port) {
    try {
      await port.open({ baudRate: 115200 }); // 메인보드 UART2와 같은 속도
    } catch (e) {
      this.error = `포트를 열 수 없어요. 다른 프로그램(CubeIDE 시리얼 모니터 등)이 쓰고 있는지 확인하세요. (${e.message})`;
      this.emit();
      return;
    }
    this.port = port;
    this.error = "";
    const info = port.getInfo();
    this.portLabel = info.usbVendorId === 0x0483 ? "STM32 (ST-Link)" : "USB 시리얼";
    this.emit();
    this.readLoop();
  }

  async readLoop() {
    const decoder = new TextDecoderStream();
    const closed = this.port.readable.pipeTo(decoder.writable).catch(() => {});
    this.reader = decoder.readable.getReader();
    let buffer = "";
    try {
      for (;;) {
        const { value, done } = await this.reader.read();
        if (done) break;
        buffer += value;
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop();
        lines.forEach((line) => this.feed(line));
      }
    } catch (e) {
      this.error = "보드 연결이 끊겼어요. USB 케이블을 확인하고 다시 연결하세요.";
    } finally {
      this.reader?.releaseLock();
      await closed;
      try { await this.port?.close(); } catch { /* 이미 닫힘 */ }
      this.port = null;
      this.emit();
    }
  }

  async disconnect() {
    try { await this.reader?.cancel(); } catch { /* 무시 */ }
  }

  stop() { super.stop(); this.disconnect(); }
}

// ---------------------------------------------------------------- 로컬 Django 서버
export class ServerSource {
  constructor(apiBase) {
    this.api = apiBase.replace(/\/$/, "");
    this.timer = null;
    this.onState = () => {};
  }
  start(onState) { this.onState = onState; this.poll(); }
  stop() { clearTimeout(this.timer); }

  async poll() {
    clearTimeout(this.timer);
    try {
      const res = await fetch(`${this.api}/api/state`, { cache: "no-store" });
      this.onState(await res.json());
    } catch {
      this.onState(null); // 서버에 닿지 않음
    }
    this.timer = setTimeout(() => this.poll(), 1000);
  }

  async post(path, body) {
    const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
    const res = await fetch(`${this.api}/api/mock/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!data.ok) alert(data.message);
    setTimeout(() => this.poll(), 150);
  }
  press(key, mood) { return this.post("press", { key, mood }); }
  tank(action, id) { return this.post("tank", { action, id }); }
  setAuto(on) { return this.post("auto", { on }); }
}
