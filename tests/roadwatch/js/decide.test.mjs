import { test } from "node:test";
import assert from "node:assert/strict";
import { golden } from "./golden.mjs";
import { Decider, legalGap, thresholds } from "../../../src/roadwatch/ui/onphone/decide.mjs";

const g = golden("decide");

test("legal gaps of TT 38/2024 as decide.legal_gap", () => {
  for (const [kmh, d] of g.legal) assert.equal(legalGap(kmh), d, `${kmh} km/h`);
});

test("alert gaps per speed as decide.thresholds", () => {
  for (const [kmh, th] of g.thresholds) assert.deepEqual(thresholds(kmh), th, `${kmh} km/h`);
});

test("every frame of a scripted drive decided exactly as decide.Decider (level, speech, reason)", () => {
  const dec = new Decider();
  for (const r of g.rows) {
    const d = dec.step(r.t, r.gap, r.ego, r.calibrated, r.ok);
    assert.deepEqual({ level: d.level, say: d.say, reason: d.reason, threshold_m: d.threshold_m, raw: [...d.raw].sort() },
                     { level: r.level, say: r.say, reason: r.reason, threshold_m: r.threshold_m, raw: r.raw }, `t = ${r.t}`);
  }
});
