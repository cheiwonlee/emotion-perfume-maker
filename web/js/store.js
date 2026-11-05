// 브라우저 안에서 보드 이벤트를 쌓아 두는 저장소.
// dashboard/sensor/services.py 를 그대로 옮긴 것이라, 만들어 내는 상태 JSON 도 Django /sensor/api/state 와 같다.
import { MOODS, PERFUMES, PERFUME_IDS, RECIPES, SCREEN_TEXT } from "./protocol.js";

const OFFLINE_AFTER_MS = 3000;
const MAX_BLENDS = 50;
const MAX_STOCK_EVENTS = 24;
const now = () => new Date().toISOString();

export class Store {
  /** @param {string|null} persistKey localStorage 에 기록을 남길 키 (null 이면 저장 안 함) */
  constructor(persistKey = null) {
    this.persistKey = persistKey;
    this.data = this.load() ?? {
      device: { screen: "", connected: false, lastSeen: null, moodCode: null },
      blends: [],   // 최신이 앞
      stock: {},    // 향료 이름 → [{ t, is_low }] (최신이 앞)
      nextId: 1,
    };
    this.data.device.connected = false;
    this.data.device.lastSeen = null;
  }

  load() {
    if (!this.persistKey) return null;
    try { return JSON.parse(localStorage.getItem(this.persistKey)); } catch { return null; }
  }

  save() {
    if (!this.persistKey) return;
    try { localStorage.setItem(this.persistKey, JSON.stringify(this.data)); } catch { /* 저장 공간이 없으면 무시 */ }
  }

  clearHistory() {
    this.data.blends = [];
    this.data.stock = {};
    this.save();
  }

  // ------------------------------------------------------------- 이벤트 반영
  handle(event) {
    if (event.kind === "status") this.updateScreen(event.screen);
    else if (event.kind === "mood") this.setMood(event.code);
    else if (event.kind === "perfume") this.recordInjection(event.name, event.ml);
    else if (event.kind === "water") this.recordWater(event.sensorId, event.isLow);
    this.save();
  }

  heartbeat(connected) {
    this.data.device.connected = connected;
    this.data.device.lastSeen = connected ? now() : this.data.device.lastSeen;
  }

  openBlend() {
    return this.data.blends.find((b) => !b.finished_at) ?? null;
  }

  updateScreen(screen) {
    const d = this.data.device;
    const previous = d.screen;
    d.screen = screen;
    this.heartbeat(true);
    if (screen === previous) return;

    const open = this.openBlend();
    if (screen === "SCREEN_BLENDING") {
      if (open) open.finished_at = now(); // 끝나지 않은 이전 제조는 중단 처리
      this.data.blends.unshift({
        id: this.data.nextId++, mood_code: d.moodCode, started_at: now(),
        finished_at: null, completed: false, injections: [],
      });
      this.data.blends.length = Math.min(this.data.blends.length, MAX_BLENDS);
    } else if (open) {
      open.finished_at = now();
      open.completed = screen === "SCREEN_FINISH";
    }
  }

  setMood(code) {
    if (MOODS[code]) this.data.device.moodCode = code;
  }

  recordInjection(perfume, ml) {
    if (!PERFUME_IDS[perfume]) return;
    const open = this.openBlend();
    if (open) open.injections.push({ perfume, ml, created_at: now() });
  }

  recordWater(sensorId, isLow) {
    const names = sensorId === 0 ? Object.values(PERFUMES) : PERFUMES[sensorId] ? [PERFUMES[sensorId]] : [];
    const value = sensorId === 0 ? false : isLow;
    for (const name of names) {
      const events = (this.data.stock[name] ??= []);
      if (events[0]?.is_low !== value) { // 값이 바뀔 때만 기록
        events.unshift({ t: now(), is_low: value });
        events.length = Math.min(events.length, MAX_STOCK_EVENTS);
      }
    }
  }

  // ------------------------------------------------------------- 화면용 상태 (Django api/state 와 같은 모양)
  blendJson(b) {
    const injected = {};
    for (const inj of b.injections) injected[inj.perfume] = (injected[inj.perfume] ?? 0) + inj.ml;
    const recipe = RECIPES[b.mood_code];
    const steps = Object.values(PERFUMES).map((name, i) => ({
      perfume: name, planned_ml: recipe ? recipe[i] : null, injected_ml: injected[name] ?? null,
    }));
    const [name, label] = MOODS[b.mood_code] ?? [null, null];
    return {
      id: b.id, mood: name, mood_label: label,
      started_at: b.started_at, finished_at: b.finished_at,
      completed: b.completed, active: !b.finished_at,
      total_ml: Object.values(injected).reduce((a, v) => a + v, 0),
      steps,
    };
  }

  snapshot() {
    const d = this.data.device;
    const online = d.connected && d.lastSeen && Date.now() - Date.parse(d.lastSeen) < OFFLINE_AFTER_MS;
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const [moodName, moodLabel] = MOODS[d.moodCode] ?? [null, null];
    const recipe = RECIPES[d.moodCode];

    return {
      device: {
        online: Boolean(online),
        screen: d.screen,
        screen_text: SCREEN_TEXT[d.screen] ?? "보드 신호를 기다리는 중",
        last_seen: d.lastSeen,
      },
      mood: d.moodCode ? {
        code: d.moodCode, name: moodName, label: moodLabel,
        recipe: recipe ? Object.fromEntries(Object.values(PERFUMES).map((n, i) => [n, recipe[i]])) : null,
      } : null,
      current_blend: this.data.blends[0] ? this.blendJson(this.data.blends[0]) : null,
      recent_blends: this.data.blends.filter((b) => b.finished_at).slice(0, 6).map((b) => this.blendJson(b)),
      today_count: this.data.blends.filter((b) => b.completed && Date.parse(b.started_at) >= today.getTime()).length,
      stock: Object.entries(PERFUMES).map(([id, name]) => {
        const events = this.data.stock[name] ?? [];
        return {
          id: Number(id), name,
          is_low: events[0]?.is_low ?? null,
          since: events[0]?.t ?? null,
          history: [...events].reverse(),
        };
      }),
    };
  }
}
