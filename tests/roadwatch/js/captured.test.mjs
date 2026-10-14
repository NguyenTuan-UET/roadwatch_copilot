import test from "node:test";
import assert from "node:assert/strict";
import { CapturedModel, F16, toF16 } from "../../../src/roadwatch/ui/onphone/captured.mjs";

globalThis.GPUBufferUsage ??= { MAP_READ: 1, COPY_SRC: 4, COPY_DST: 8, STORAGE: 128 };
globalThis.GPUMapMode ??= { READ: 1 };
const IMG = 2 * 6 * 128 * 256, STATE = 2 * 5 * 6 * 128 * 256;

/* WebGPU giả: bộ đệm là mảng byte, writeBuffer chép ngay, lệnh chép chạy khi submit. */
function fakeDevice() {
  const buffers = [];
  const device = {
    buffers,
    createBuffer({ size }) {
      const b = { size, bytes: new Uint8Array(size), destroyed: false,
        async mapAsync() {}, getMappedRange: (o = 0, n = size) => b.bytes.slice(o, o + n).buffer, unmap() {}, destroy() { b.destroyed = true; } };
      buffers.push(b); return b;
    },
    queue: {
      writeBuffer(b, offset, data) { b.bytes.set(new Uint8Array(data.buffer, data.byteOffset, data.byteLength), offset); },
      submit(list) { for (const cmds of list) for (const [src, so, dst, d, n] of cmds) dst.bytes.set(src.bytes.subarray(so, so + n), d); },
    },
    createCommandEncoder() { const cmds = []; return { copyBufferToBuffer: (...a) => cmds.push(a), finish: () => cmds }; },
  };
  return device;
}
const fakeOrt = { Tensor: { fromGpuBuffer: (gpuBuffer, { dataType, dims }) => ({ gpuBuffer, dataType, dims }) } };

/* Model giả trên bộ đệm GPU: outputs[0] = số lần chạy, outputs[1] = bit float16 đầu tiên của new_img,
   outputs[2] = 2 byte đầu của state_img_q; next_state = state + 1 ở byte đầu. */
function fakeSession(inputNames = ["new_img", "state_img_q"]) {
  const s = { calls: [], released: false, inputNames,
    async run(feeds, fetches) {
      s.calls.push([feeds, fetches]);
      const img = new Uint16Array(feeds.new_img.gpuBuffer.bytes.buffer), st = feeds.state_img_q.gpuBuffer.bytes;
      const out = new Float32Array(fetches.outputs.gpuBuffer.bytes.buffer);
      out[0] = s.calls.length; out[1] = img[0]; out[2] = st[0] | (st[1] << 8);
      const next = fetches.next_state_img_q.gpuBuffer.bytes; next.set(st); next[0] = st[0] + 1;
    },
    async release() { s.released = true; } };
  return s;
}

test("toF16 gives the float16 bits of every uint8 value", () => {
  for (let v = 0; v < 256; v++) {
    const h = F16[v], e = (h >> 10) & 31, m = h & 1023;
    assert.equal(e ? 2 ** (e - 15) * (1 + m / 1024) : 0, v);
  }
  assert.deepEqual([...toF16(new Uint8Array([0, 1, 255]))], [0, 0x3c00, 0x5bf8]);
});

test("every frame reuses the same GPU buffers (graph capture replays on them) and feeds the state back on the GPU", async () => {
  const device = fakeDevice(), session = fakeSession(), m = new CapturedModel(fakeOrt, session, device);
  const frame = new Uint8Array(IMG); frame[0] = 1;
  const a = await m.run(frame), b = await m.run(frame);
  assert.equal(a.length, 707);
  assert.deepEqual([a[0], a[1], a[2]], [1, 0x3c00, 0]);   // new_img float16; state starts at 0
  assert.deepEqual([b[0], b[2]], [2, 1]);                  // the state the first run wrote
  const [[f1, o1], [f2, o2]] = session.calls;
  assert.equal(f1, f2); assert.equal(o1, o2);
  assert.equal(f1.new_img.dataType, "float16"); assert.equal(f1.state_img_q.gpuBuffer.size, 2 * STATE);
  assert.equal(o1.outputs.dataType, "float32");
});

test("reset starts a new run from an empty state, release frees the buffers and the session", async () => {
  const device = fakeDevice(), session = fakeSession(), m = new CapturedModel(fakeOrt, session, device);
  await m.run(new Uint8Array(IMG)); await m.run(new Uint8Array(IMG));
  m.reset();
  assert.equal((await m.run(new Uint8Array(IMG)))[2], 0);
  await m.release();
  assert.ok(session.released && device.buffers.every((b) => b.destroyed));
});

/* Model có nhánh policy: desire, traffic_convention cố định; hai hàng đợi trạng thái float32 chuyền qua các khung. */
function policySession() {
  const s = fakeSession(["new_img", "desire", "traffic_convention", "state_img_q", "state_desire_q", "state_feat_q"]);
  const run = s.run;
  s.run = async (feeds, fetches) => {
    await run(feeds, fetches);
    const f32 = (t) => new Float32Array(t.gpuBuffer.bytes.buffer);
    const out = f32(fetches.outputs);
    out[3] = f32(feeds.traffic_convention)[0]; out[4] = f32(feeds.desire)[0]; out[5] = f32(feeds.state_feat_q)[0];
    out[1960] = 7;
    const next = f32(fetches.next_state_feat_q); next.set(f32(feeds.state_feat_q)); next[0] += 1;
    f32(fetches.next_state_desire_q).set(f32(feeds.state_desire_q));
  };
  return s;
}

test("a model with the policy branch: 1961 outputs, desire 0, right-hand traffic, its queues fed back on the GPU", async () => {
  const device = fakeDevice(), session = policySession(), m = new CapturedModel(fakeOrt, session, device);
  const a = await m.run(new Uint8Array(IMG)), b = await m.run(new Uint8Array(IMG));
  assert.equal(a.length, 1961);
  assert.deepEqual([a[3], a[4], a[5], a[1960]], [1, 0, 0, 7]);
  assert.equal(b[5], 1);
  const [[f1, o1]] = session.calls;
  assert.deepEqual(f1.state_feat_q.dims, [96, 1, 512]); assert.equal(f1.state_feat_q.dataType, "float32");
  assert.deepEqual(o1.outputs.dims, [1, 1961]);
  m.reset();
  assert.equal((await m.run(new Uint8Array(IMG)))[5], 0);
});
