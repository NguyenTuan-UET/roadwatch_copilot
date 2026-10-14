import test from "node:test";
import assert from "node:assert/strict";
import { loadPhoneModel } from "../../../src/roadwatch/ui/onphone/backend.mjs";

test("auto uses WebGPU when its model loads", async () => {
  const calls = [];
  const result = await loadPhoneModel(async (ep, url) => { calls.push([ep, url]); return { ep }; }, "auto");
  assert.equal(result.ep, "webgpu");
  assert.deepEqual(calls, [["webgpu", "/ortweb/gr14VinAI.capture.onnx"]]);
});

test("auto retries with FP32 on CPU after WebGPU load failure", async () => {
  const calls = [], notes = [];
  const result = await loadPhoneModel(async (ep, url) => {
    calls.push([ep, url]);
    if (ep === "webgpu") throw new Error("no GPU adapter");
    return { ep };
  }, "auto", (note) => notes.push(note));
  assert.equal(result.ep, "wasm");
  assert.deepEqual(calls, [["webgpu", "/ortweb/gr14VinAI.capture.onnx"], ["wasm", "/ortweb/gr14VinAI.fp32.onnx"]]);
  assert.match(notes[0], /CPU/);
});

test("CPU selection never attempts WebGPU", async () => {
  const calls = [];
  await loadPhoneModel(async (ep, url) => { calls.push([ep, url]); return {}; }, "wasm");
  assert.deepEqual(calls, [["wasm", "/ortweb/gr14VinAI.fp32.onnx"]]);
});
