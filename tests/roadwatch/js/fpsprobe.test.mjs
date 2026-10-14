import test from "node:test";
import assert from "node:assert/strict";
import { estimateFps, fpsHint } from "../../../src/roadwatch/ui/fpsprobe.mjs";

const clock = (fps, n = 40, jitter = 0) => Array.from({ length: n }, (_, i) => i / fps + (i % 2 ? jitter : -jitter));

test("estimateFps snaps the frame rate to a standard one", () => {
  for (const [fps, want] of [[29.97, 29.97], [30, 30], [25, 25], [23.976, 23.976], [59.94, 59.94], [20, 20]])
    assert.equal(estimateFps(clock(fps, 40)), want, String(fps));
  assert.equal(estimateFps(clock(25, 40, 0.0002)), 25);   // timestamps with a little noise
});

test("dropped frames (a slow decoder) do not change the answer", () => {
  const t = clock(29.97, 120).filter((_, i) => i % 7 !== 3 && i % 11 !== 5);   // some frames never presented
  assert.equal(estimateFps(t), 29.97);
});

test("a rate that matches no standard one is reported as measured; too few frames give null", () => {
  assert.equal(estimateFps(clock(17, 40)), 17);
  assert.equal(estimateFps([0, 0.03]), null);
  assert.equal(estimateFps([]), null);
  assert.equal(estimateFps([1, 1, 1, 1, 1, 1]), null);
});

test("the hint says whether the entered fps fits the video (within 5 %)", () => {
  assert.deepEqual(fpsHint(29.97, 20), { ok: false, text: "Video này khoảng 29,97 fps, đang nhập 20: vận tốc sẽ sai khoảng 1,5 lần." });
  assert.equal(fpsHint(29.97, 30).ok, true);
  assert.equal(fpsHint(null, 20).text, "");
  assert.equal(fpsHint(25, NaN).ok, false);
});
