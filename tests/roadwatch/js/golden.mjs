/* Dữ liệu chuẩn do scripts/roadwatch/export_onphone_golden.py xuất từ code Python. */
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

export const golden = (name) => JSON.parse(readFileSync(new URL(`../fixtures/onphone/${name}.json`, import.meta.url)));
export const bytes = (b64) => new Uint8Array(Buffer.from(b64, "base64"));
export const floats = (b64) => { const b = Buffer.from(b64, "base64"); return new Float32Array(b.buffer, b.byteOffset, b.length / 4); };

/** a ≈ b (số, null, mảng lồng) trong sai số tuyệt đối atol + tương đối rtol; path để báo chỗ lệch. */
export function close(a, b, { atol = 1e-9, rtol = 1e-9 } = {}, path = "") {
  if (b === null || a === null) return assert.equal(a, b, `${path}: ${a} vs ${b}`);
  if (Array.isArray(b)) {
    assert.equal(a.length, b.length, `${path}: length`);
    b.forEach((v, i) => close(a[i], v, { atol, rtol }, `${path}[${i}]`));
    return;
  }
  assert.ok(Math.abs(a - b) <= atol + rtol * Math.abs(b), `${path}: ${a} vs ${b}`);
}
