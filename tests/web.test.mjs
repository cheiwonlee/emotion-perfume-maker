// 브라우저 대시보드의 파서·저장소 테스트.  실행: node --test tests/
import assert from "node:assert/strict";
import test from "node:test";
import { parseLine } from "../web/js/protocol.js";
import { Store } from "../web/js/store.js";

test("펌웨어가 출력하는 줄을 이벤트로 바꾼다", () => {
  assert.deepEqual(parseLine("STATUS : SCREEN_BLENDING"), { kind: "status", screen: "SCREEN_BLENDING" });
  assert.deepEqual(parseLine("MOOD : 2"), { kind: "mood", code: 2 });
  assert.deepEqual(parseLine("PERFUME : Lavender : 4"), { kind: "perfume", name: "Lavender", ml: 4 });
  assert.deepEqual(parseLine("WATER_X : 3\r"), { kind: "water", sensorId: 3, isLow: true });
  assert.deepEqual(parseLine("WATER_O : 0"), { kind: "water", sensorId: 0, isLow: false });
  for (const l of ["", "System Ready.", "Waiting for reply (Rx_ID = 121)...", "MOOD : abc"]) assert.equal(parseLine(l), null);
});

test("제조 흐름을 Django 와 같은 상태로 만든다", () => {
  const s = new Store();
  for (const l of ["MOOD : 2", "STATUS : SCREEN_CONFIRM", "STATUS : SCREEN_BLENDING",
    "PERFUME : Lavender : 8", "PERFUME : Cedarwood : 4", "PERFUME : Vanilla : 2", "PERFUME : Bergamot : 2",
    "STATUS : SCREEN_FINISH"]) s.handle(parseLine(l));
  const st = s.snapshot();
  assert.equal(st.device.online, true);
  assert.equal(st.mood.name, "Calm");
  assert.equal(st.recent_blends[0].total_ml, 16);
  assert.equal(st.recent_blends[0].completed, true);
  assert.equal(st.today_count, 1);
});

test("중간에 멈춘 제조는 완성으로 세지 않는다", () => {
  const s = new Store();
  for (const l of ["MOOD : 4", "STATUS : SCREEN_BLENDING", "PERFUME : Lavender : 4", "WATER_X : 3", "STATUS : SCREEN_MOODSELECT"])
    s.handle(parseLine(l));
  const st = s.snapshot();
  assert.equal(st.recent_blends[0].completed, false);
  assert.equal(st.today_count, 0);
  assert.equal(st.stock[2].is_low, true);
});

test("수위는 바뀔 때만 기록하고, 0 은 전체 충분", () => {
  const s = new Store();
  ["WATER_X : 3", "WATER_X : 3", "WATER_O : 0"].forEach((l) => s.handle(parseLine(l)));
  assert.equal(s.snapshot().stock[2].history.length, 2);
  assert.ok(s.snapshot().stock.every((x) => x.is_low === false));
});
