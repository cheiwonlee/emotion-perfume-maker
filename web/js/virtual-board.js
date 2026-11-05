// 브라우저 안에서 도는 가상 보드. mock/ (Python) 과 같은 동작을 JavaScript 로 옮긴 것이다.
//   메인보드: 터치 LCD 상태 머신, 레시피, 회전판, LoRa 마스터, 시리얼 출력
//   서브보드: 작업 패킷 처리, 수위 확인(LOW 거절), 주사기 모터, DONE/LVL 응답
// LoRa 패킷은 펌웨어와 바이트 단위로 같다. (protocol 설명은 mock/protocol.py 참고)
import { MOODS, PERFUMES, RECIPES } from "./protocol.js";

const PACKET_ID = 121;
const ONE_CYCLE = 4096;
const RX_TIMEOUT_MS = 1000;
const LEVEL_QUERY_INTERVAL_MS = 30000;
const LEVEL = { LOW: 0, OK: 1, UNKNOWN: 0xff };
const enc = new TextEncoder();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 화면 상태 (main.c UI_State_t)
const S = { START: 0, MOOD_SELECT: 1, CONFIRM: 2, BLENDING: 3, FINISH: 4 };
const STATUS_NAMES = ["SCREEN_START", "SCREEN_MOODSELECT", "SCREEN_CONFIRM", "SCREEN_BLENDING", "SCREEN_FINISH"];
// DecodeMoodFromTouch(): 기분 → 터치 키 비트
const MOOD_KEY_BIT = { 1: 7, 2: 3, 3: 6, 4: 2, 5: 5, 6: 1, 7: 4, 8: 0 };
const KEY_START = 1 << 0;
const KEY_BACK = 1 << 4;
const BOTTLE_ANGLES = { 1: 0, 2: 90, 3: 180, 4: 270 };

export const moodToTouch = (mood) => 1 << MOOD_KEY_BIT[mood];
function decodeMood(touch) {
  for (let mood = 1; mood <= 8; mood++) if (touch & moodToTouch(mood)) return mood;
  return 0;
}

// --------------------------------------------------------------------------- 시간 / 통신 / 부품
class Clock {
  constructor(speed) { this.speed = speed; this.t0 = performance.now(); }
  delay(ms) { return sleep(ms / this.speed); }
  tick() { return (performance.now() - this.t0) * this.speed; }
}

class Channel {
  constructor(airtimeMs) { this.airtimeMs = airtimeMs; this.nodes = []; }
  send(from, bytes) {
    setTimeout(() => this.nodes.forEach((n) => n !== from && n.onRx?.(bytes)), this.airtimeMs);
  }
}

class Radio {
  constructor(channel) { this.channel = channel; this.onRx = null; channel.nodes.push(this); }
  send(bytes) { this.channel.send(this, Uint8Array.from(bytes)); }
}

class AsyncQueue {
  constructor() { this.items = []; this.waiters = []; }
  put(item) { const w = this.waiters.shift(); w ? w(item) : this.items.push(item); }
  clear() { this.items = []; }
  get(timeoutMs = Infinity) {
    if (this.items.length) return Promise.resolve(this.items.shift());
    return new Promise((resolve) => {
      const waiter = (item) => { clearTimeout(timer); resolve(item); };
      const timer = timeoutMs === Infinity ? null : setTimeout(() => {
        this.waiters = this.waiters.filter((w) => w !== waiter);
        resolve(null);
      }, timeoutMs);
      this.waiters.push(waiter);
    });
  }
}

class Tanks {
  constructor(capacity = 30, lowLevel = 5) {
    this.capacity = capacity; this.lowLevel = lowLevel;
    this.levels = { 1: capacity, 2: capacity, 3: capacity, 4: capacity };
  }
  take(id, ml) { this.levels[id] = Math.max(0, this.levels[id] - ml); }
  isLow(id) { return this.levels[id] < this.lowLevel; }
  drain(id) { this.levels[id] = 0; }
  refill(id) { for (const k of id ? [id] : [1, 2, 3, 4]) this.levels[k] = this.capacity; }
}

class TouchLcd {
  constructor() { this.buffer = []; this.screen = ["BOOT", []]; this.touches = []; }
  clear() { this.buffer = []; }
  draw(x, y, text) { this.buffer.push({ x, y, text: text.slice(0, 16) }); }
  flush(title) { this.screen = [title, [...this.buffer]]; }
  press(mask) { this.touches.push(mask); }
}

// --------------------------------------------------------------------------- 패킷 (펌웨어와 동일한 바이트)
function jobPacket(sensorId, ml) {
  const b = new Uint8Array(9);
  const v = new DataView(b.buffer);
  b[0] = PACKET_ID; v.setInt32(1, sensorId, true); v.setFloat32(5, ml, true);
  return b;
}
const tagIs = (p, tag, at = 1) => tag.split("").every((c, i) => p[at + i] === c.charCodeAt(0));

// --------------------------------------------------------------------------- 서브보드
class SubBoard {
  constructor(radio, clock, tanks, rxId) {
    this.radio = radio; this.clock = clock; this.tanks = tanks; this.rxId = rxId;
    this.queue = new AsyncQueue();
    radio.onRx = (p) => this.queue.put(p);
    this.loop();
  }
  readLevel(id) { return id in this.tanks.levels ? (this.tanks.isLow(id) ? LEVEL.LOW : LEVEL.OK) : LEVEL.UNKNOWN; }
  async loop() {
    for (;;) {
      const p = await this.queue.get();
      if (p[0] !== this.rxId) continue;
      if (p.length === 5 && tagIs(p, "LVL?")) { // SendLevels()
        const levels = [1, 2, 3, 4].map((id) => this.readLevel(id));
        this.radio.send([this.rxId, ...enc.encode("LVL"), ...levels]);
        continue;
      }
      if (p.length !== 9) continue; // START 패킷 등은 무시
      const view = new DataView(p.buffer);
      await this.runJob(view.getInt32(1, true), view.getFloat32(5, true));
    }
  }
  async runJob(id, ml) { // RunJob()
    if (this.readLevel(id) === LEVEL.LOW) {
      this.radio.send([this.rxId, ...enc.encode("LOW"), id]);
      return;
    }
    await this.clock.delay(ml * ONE_CYCLE * 1); // 스텝당 1ms
    this.tanks.take(id, ml);
    this.radio.send([this.rxId, ...enc.encode("DONE"), this.readLevel(id)]);
  }
}

// --------------------------------------------------------------------------- 메인보드
class MainBoard {
  constructor(radio, clock, lcd, onLine) {
    this.radio = radio; this.clock = clock; this.lcd = lcd; this.printf = onLine;
    this.state = S.START; this.needsRedraw = true; this.selectedMood = 0;
    this.angle = 0; this.lastTouch = -1e9; this.lastLevelQuery = 0; this.stopped = false;
    this.rx = new AsyncQueue();
    radio.onRx = (p) => this.rx.put(p);
  }

  async main() {
    this.printf("Combined UI & Motor Controller (Queue Ver)");
    await this.clock.delay(2500);
    this.printf("System Ready.");
    while (!this.stopped) {
      if (this.needsRedraw) {
        this.needsRedraw = false;
        if (this.state === S.START) { this.drawStart(); await this.queryLevels(); }
        else if (this.state === S.MOOD_SELECT) this.drawMoodSelect();
        else if (this.state === S.CONFIRM) this.drawConfirm();
        else if (this.state === S.BLENDING) { this.drawBlending(); await this.runBlending(this.selectedMood); }
        else if (this.state === S.FINISH) this.drawFinish();
      }
      if (this.state !== S.BLENDING && this.lcd.touches.length && this.clock.tick() - this.lastTouch > 200) {
        await this.processTouch(this.lcd.touches.shift());
        this.lastTouch = this.clock.tick();
      }
      if (this.state === S.START && !this.needsRedraw && this.clock.tick() - this.lastLevelQuery > LEVEL_QUERY_INTERVAL_MS) {
        await this.queryLevels();
      }
      await this.clock.delay(10);
    }
  }

  async processTouch(touch) {
    this.printf(`ProcessTouch: 0x${touch.toString(16).padStart(2, "0").toUpperCase()} (state=${this.state})`);
    if (this.state === S.START) { this.state = S.MOOD_SELECT; this.needsRedraw = true; }
    else if (this.state === S.MOOD_SELECT) {
      let mood = decodeMood(touch);
      if (mood === 8) mood = (Math.floor(this.clock.tick()) % 7) + 1; // Random
      if (!mood) return;
      this.selectedMood = mood;
      this.printf(`MOOD : ${mood}`);
      this.state = S.CONFIRM; this.needsRedraw = true;
    } else if (this.state === S.CONFIRM) {
      if (touch & KEY_BACK) { this.state = S.MOOD_SELECT; this.needsRedraw = true; }
      else if (touch & KEY_START) {
        this.printf(`LoRa: SEND START (mood=${this.selectedMood})`);
        this.radio.send([PACKET_ID, ...enc.encode("START"), this.selectedMood]);
        this.state = S.BLENDING; this.needsRedraw = true;
      }
    } else if (this.state === S.FINISH) { this.state = S.START; this.selectedMood = 0; this.needsRedraw = true; }
    if (this.needsRedraw) await this.clock.delay(300);
  }

  async runBlending(mood) {
    this.printf(`>>> Blending Start: Mood ${mood} <<<`);
    const recipe = RECIPES[mood];
    if (!recipe) { this.state = S.MOOD_SELECT; this.needsRedraw = true; return; }
    for (let id = 1; id <= 4; id++) {
      const reply = await this.injectPerfume(id, recipe[id - 1]);
      if (reply !== "DONE") {
        this.drawMessage(...(reply === "LOW" ? ["Refill needed:", PERFUMES[id]] : ["No reply from", "syringe board"]));
        await this.clock.delay(2500);
        this.angle = 0;
        this.state = S.MOOD_SELECT; this.needsRedraw = true;
        return;
      }
    }
    this.printf(">>> Blending Complete! <<<");
    this.angle = 0;
    this.state = S.FINISH; this.needsRedraw = true;
  }

  async injectPerfume(id, ml) { // InjectPerfume()
    let move = BOTTLE_ANGLES[id] - this.angle;
    if (move > 180) move -= 360;
    if (move < -180) move += 360;
    await this.clock.delay(Math.abs(Math.trunc((1024 * move) / 90)) * 2); // 회전판 이동
    this.angle = (this.angle + move + 360) % 360;

    this.printf(`PERFUME : ${PERFUMES[id]} : ${Math.trunc(ml)}`);
    this.rx.clear();
    this.radio.send(jobPacket(id, ml));

    const timeout = ml * ONE_CYCLE * 2 + 10000;
    const start = this.clock.tick();
    while (this.clock.tick() - start < timeout) {
      const p = await this.rx.get(RX_TIMEOUT_MS / this.clock.speed);
      if (!p || p[0] !== PACKET_ID) continue;
      if (p.length >= 5 && tagIs(p, "DONE")) {
        const level = p.length >= 6 ? p[5] : LEVEL.UNKNOWN;
        if (level === LEVEL.LOW) this.printf(`WATER_X : ${id}`);
        else if (level === LEVEL.OK) this.printf(`WATER_O : ${id}`);
        return "DONE";
      }
      if (p.length >= 5 && tagIs(p, "LOW")) { this.printf(`WATER_X : ${id}`); return "LOW"; }
    }
    return "TIMEOUT";
  }

  async queryLevels() { // QueryLevels()
    this.lastLevelQuery = this.clock.tick();
    this.rx.clear();
    this.radio.send([PACKET_ID, ...enc.encode("LVL?")]);
    const start = this.clock.tick();
    while (this.clock.tick() - start < 2000) {
      const p = await this.rx.get(RX_TIMEOUT_MS / this.clock.speed);
      if (p && p[0] === PACKET_ID && p.length >= 8 && tagIs(p, "LVL")) {
        for (let id = 1; id <= 4; id++) {
          if (p[3 + id] === LEVEL.LOW) this.printf(`WATER_X : ${id}`);
          else if (p[3 + id] === LEVEL.OK) this.printf(`WATER_O : ${id}`);
        }
        return;
      }
    }
  }

  // 화면 (main.c Draw_Screen_*)
  status() { this.printf(`STATUS : ${STATUS_NAMES[this.state]}`); }
  drawStart() {
    const l = this.lcd; l.clear();
    l.draw(25, 30, "DAILY MOOD"); l.draw(13, 48, "PERFUME MAKER"); l.draw(5, 104, "Tap to continue");
    l.flush("START"); this.status();
  }
  drawMoodSelect() {
    const l = this.lcd; l.clear();
    [[6, 6], [74, 6], [6, 40], [74, 40], [6, 74], [74, 74], [6, 108], [74, 108]]
      .forEach(([x, y], i) => l.draw(x, y, MOODS[i + 1][0]));
    l.flush("MOOD SELECT"); this.status();
  }
  drawConfirm() {
    const l = this.lcd; l.clear();
    l.draw(20, 40, `Mood: ${MOODS[this.selectedMood][0]}`); l.draw(7, 106, "[Back]"); l.draw(70, 106, "[Start]");
    l.flush("CONFIRM"); this.status();
  }
  drawBlending() {
    const l = this.lcd; l.clear();
    l.draw(20, 50, "Blending..."); l.draw(20, 70, "Please wait!");
    l.flush("BLENDING"); this.status();
  }
  drawFinish() {
    const l = this.lcd; l.clear();
    l.draw(40, 15, "Finish!"); l.draw(16, 40, "Your perfume"); l.draw(15, 60, "is now ready."); l.draw(22, 104, "Tap to home");
    l.flush("FINISH"); this.status();
  }
  drawMessage(a, b) {
    const l = this.lcd; l.clear(); l.draw(10, 40, a); l.draw(10, 60, b); l.flush("MESSAGE");
  }
}

// --------------------------------------------------------------------------- 전체 조립 + 조작
export class VirtualBoard {
  /** @param {(line: string) => void} onLine 메인보드가 시리얼로 내보내는 줄 */
  constructor(onLine, { speed = 5 } = {}) {
    this.clock = new Clock(speed);
    const channel = new Channel(30 / speed);
    this.tanks = new Tanks();
    this.lcd = new TouchLcd();
    this.sub = new SubBoard(new Radio(channel), this.clock, this.tanks, PACKET_ID);
    this.main = new MainBoard(new Radio(channel), this.clock, this.lcd, onLine);
    this.autoOn = false;
    this.main.main();
  }

  stop() { this.main.stopped = true; this.autoOn = false; }

  snapshot() {
    const [title, cells] = this.lcd.screen;
    return {
      screen: STATUS_NAMES[this.main.state],
      lcd: { title, cells },
      tanks: Object.entries(PERFUMES).map(([id, name]) => ({
        id: Number(id), name, ml: Math.round(this.tanks.levels[id] * 10) / 10,
        capacity: this.tanks.capacity, low_level: this.tanks.lowLevel, is_low: this.tanks.isLow(id),
      })),
      auto: this.autoOn,
      speed: this.clock.speed,
    };
  }

  press(key, mood) {
    if (key === "mood") this.lcd.press(moodToTouch(mood));
    else this.lcd.press({ tap: 0x01, start: KEY_START, back: KEY_BACK }[key]);
  }

  tank(action, id) {
    if (action === "drain") this.tanks.drain(id);
    else this.tanks.refill(id);
  }

  // ---- 자동 시연
  setAuto(on) {
    if (on === this.autoOn) return;
    this.autoOn = on;
    if (on) this.autoLoop();
  }
  async waitState(states, ms = 120000) {
    const end = performance.now() + ms;
    while (performance.now() < end) {
      if (states.includes(this.main.state) && !this.main.needsRedraw) return true;
      await sleep(50);
    }
    return false;
  }
  async pause(ms) {
    const end = performance.now() + ms;
    while (performance.now() < end) { if (!this.autoOn) return false; await sleep(100); }
    return this.autoOn;
  }
  async makeOne(mood) {
    const m = this.main;
    if (m.state === S.FINISH) { this.press("tap"); await this.waitState([S.START]); }
    if (m.state === S.START) { this.press("tap"); await this.waitState([S.MOOD_SELECT]); }
    if (m.state === S.CONFIRM) { this.press("back"); await this.waitState([S.MOOD_SELECT]); }
    this.press("mood", mood); await this.waitState([S.CONFIRM]);
    this.press("start"); await sleep(500);
    await this.waitState([S.FINISH, S.MOOD_SELECT]);
  }
  async autoLoop() {
    await this.waitState([S.START, S.MOOD_SELECT, S.FINISH, S.CONFIRM], 30000);
    for (let cycle = 1; this.autoOn; cycle++) {
      await this.makeOne(1 + Math.floor(Math.random() * 8));
      if (!(await this.pause(3000))) return;
      if (cycle % 3 === 0) { // 세 번에 한 번은 통 하나를 비웠다가 다시 채움
        this.tanks.drain(1 + Math.floor(Math.random() * 4));
        if (!(await this.pause(6000))) return;
        this.tanks.refill();
        if (!(await this.pause(3000))) return;
      }
    }
  }
}
