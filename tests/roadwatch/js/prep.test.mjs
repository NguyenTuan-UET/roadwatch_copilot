import { test } from "node:test";
import assert from "node:assert/strict";
import { bytes, golden } from "./golden.mjs";
import { frameToModelInput, packFrame, prepFromRGBA, rgbaToI420, sampleRect, shiftWarps } from "../../../src/roadwatch/ui/onphone/prep.mjs";
import { intrinsics, warpMatrices } from "../../../src/roadwatch/ui/onphone/geometry.mjs";

const g = golden("prep");
function planes(w, h) {   // giống planes() trong export_onphone_golden.py
  const y = new Uint8Array(w * h), u = new Uint8Array((w / 2) * (h / 2)), v = new Uint8Array(u.length);
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) y[j * w + i] = (i * 3 + j * 5 + ((i * j) % 7)) % 256;
  for (let j = 0; j < h / 2; j++) for (let i = 0; i < w / 2; i++) { u[j * (w / 2) + i] = (i + j * 2) % 256; v[j * (w / 2) + i] = (i * 3 + j) % 256; }
  return { y, u, v };
}
function diff(a, b) {
  let max = 0, sum = 0, off = 0;
  for (let i = 0; i < a.length; i++) { const d = Math.abs(a[i] - b[i]); max = Math.max(max, d); sum += d; off += d > 0; }
  return { max, mean: sum / a.length, off: off / a.length };
}

test("warp into the model frame ≈ cv2.warpPerspective (5-bit fixed-point coordinates there)", () => {
  const p = planes(g.w, g.h);
  const one = diff(frameToModelInput(p, g.w, g.h, g.narrow), bytes(g.single));
  const both = diff(packFrame(p, g.w, g.h, [g.narrow, g.wide]), bytes(g.packed));
  // cv2 interpolates with 5-bit fixed-point coordinates: 0.01 % of the pixels differ by 1 level (13/10/2026)
  for (const d of [one, both]) assert.ok(d.max <= 1 && d.off < 0.001, JSON.stringify(d));
});

test("RGB -> I420 as cv2.COLOR_RGB2YUV_I420 (BT.601 limited, top-left chroma)", () => {
  const rgb = bytes(g.rgb), want = bytes(g.i420), rgba = new Uint8ClampedArray(16 * 16 * 4);
  for (let i = 0; i < 256; i++) rgba.set([rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2], 255], 4 * i);
  const { y, u, v } = rgbaToI420(rgba, 16, 16);
  const d = diff(Uint8Array.from([...y, ...u, ...v]), want);
  assert.ok(d.max <= 1, JSON.stringify(d));
});

test("warping straight from RGBA = RGBA -> I420 then warp (what the phone does, without converting the whole picture)", () => {
  const w = 1280, h = 960, rgba = new Uint8ClampedArray(w * h * 4);
  for (let j = 0, p = 0; j < h; j++) for (let i = 0; i < w; i++, p += 4) rgba.set([(i * 7 + j) % 256, (j * 3 + (i >> 2)) % 256, ((i * j) >> 5) % 256, 255], p);
  const warps = warpMatrices(intrinsics(962, w, h), [0.01, 0.06, -0.04], w, "warp");   // narrow and wide
  const want = packFrame(rgbaToI420(rgba, w, h), w, h, warps);
  let t = performance.now();
  const got = prepFromRGBA(rgba, w, h, warps);
  t = performance.now() - t;
  const d = diff(got, want);
  console.log("prepFromRGBA", d, `${t.toFixed(1)} ms (node, laptop)`);
  assert.ok(d.max <= 1 && d.off < 0.01, JSON.stringify(d));
  assert.ok(want.filter((x) => x !== 0).length > 0.95 * want.length, "the warps sample inside the picture");
});

test("reading only the picture region the model samples gives the same input (less memory on the phone)", () => {
  const w = 1280, h = 960, rgba = new Uint8ClampedArray(w * h * 4);
  for (let j = 0, p = 0; j < h; j++) for (let i = 0; i < w; i++, p += 4) rgba.set([(i * 7 + j) % 256, (j * 3 + (i >> 2)) % 256, ((i * j) >> 5) % 256, 255], p);
  for (const [rpy, mode] of [[[0.01, 0.06, -0.04], "dup"], [[0, -0.12, 0.2], "dup"], [[0.01, 0.06, -0.04], "warp"]]) {
    const warps = warpMatrices(intrinsics(962, w, h), rpy, w, mode);
    const full = prepFromRGBA(rgba, w, h, warps);
    const [x0, y0, cw, ch] = sampleRect(warps, w, h);
    const sub = new Uint8ClampedArray(cw * ch * 4);
    for (let j = 0; j < ch; j++) sub.set(rgba.subarray(4 * ((y0 + j) * w + x0), 4 * ((y0 + j) * w + x0 + cw)), 4 * j * cw);
    const crop = prepFromRGBA(sub, cw, ch, shiftWarps(warps, x0, y0));
    assert.deepEqual(diff(crop, full), { max: 0, mean: 0, off: 0 }, `${rpy} ${mode}`);
    if (mode === "dup") assert.ok(cw * ch < 0.5 * w * h, `dup reads ${cw}x${ch} of ${w}x${h}`);
  }
});
