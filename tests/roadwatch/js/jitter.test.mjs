import test from "node:test";
import assert from "node:assert/strict";
import { Jitter } from "../../../src/roadwatch/ui/onphone/jitter.mjs";

test("a straight line has no jitter; a zigzag does, in m/s^2 per second squared (a slower frame rate gives smaller numbers for the same zigzag)", () => {
  const line = new Jitter(), zig = new Jitter(), zig10 = new Jitter();
  for (let i = 0; i < 100; i++) { line.add(i / 20, 1 + 0.02 * i); zig.add(i / 20, i % 2 ? 0.1 : 0); zig10.add(i / 10, i % 2 ? 0.1 : 0); }
  assert.ok(line.summary().accel_rms < 1e-9);
  const a = zig.summary(), b = zig10.summary();
  assert.ok(Math.abs(a.accel_rms - 0.2 * 400) < 1e-6);   // |second difference| = 0.2, dt = 0.05: 0.2 / dt^2
  assert.ok(Math.abs(b.accel_rms - 0.2 * 100) < 1e-6);
  assert.equal(a.n, 100);
});

test("summary of few samples is null, and reset starts again", () => {
  const j = new Jitter(); j.add(0, 1); j.add(0.05, 2);
  assert.equal(j.summary().accel_rms, null);
  j.add(0.1, 3); assert.equal(j.summary().n, 3);
  j.reset(); assert.equal(j.summary().n, 0);
});
