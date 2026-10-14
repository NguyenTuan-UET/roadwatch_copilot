import test from "node:test";
import assert from "node:assert/strict";
import { FrameModel } from "../../../src/roadwatch/ui/onphone/inference.mjs";

let made = [];
class Tensor {
  constructor(type, data, dims) { Object.assign(this, { type, data, dims, disposed: false }); made.push(this); }
  dispose() { assert.equal(this.disposed, false, "disposed twice"); this.disposed = true; }
}
const ort = { Tensor };

/* Phiên giả: outputs[0] = phần tử đầu của new_img, [1] = của state_img_q, [2] = traffic_convention[0],
   [3] = state_feat_q[0]; next_state_* = state + 1 ở phần tử đầu. */
function session(inputNames, n = 707) {
  const s = { inputNames, released: false, feeds: [],
    async run(feeds) {
      s.feeds.push(feeds);
      if (s.fail) throw new Error("run failed");
      const out = new Float32Array(n);
      out[0] = feeds.new_img.data[0]; out[1] = feeds.state_img_q.data[0];
      if (feeds.traffic_convention) { out[2] = feeds.traffic_convention.data[0]; out[3] = feeds.state_feat_q.data[0]; }
      const next = (t) => { const d = t.data.slice(); d[0] += 1; return new Tensor(t.type, d, t.dims); };
      const o = { outputs: new Tensor("float32", out, [1, n]) };
      for (const k of inputNames) if (k.startsWith("state_")) o["next_" + k] = next(feeds[k]);
      return o;
    },
    async release() { s.released = true; } };
  return s;
}

test("each frame feeds the previous state back and releases every tensor it no longer needs", async () => {
  made = [];
  const sess = session(["new_img", "state_img_q"]), m = new FrameModel(ort, sess);
  const frame = new Uint8Array(2 * 6 * 128 * 256); frame[0] = 9;
  const a = await m.run(frame), b = await m.run(frame);
  assert.deepEqual([a[0], a[1], b[1]], [9, 0, 1]);
  assert.equal(sess.feeds[0].new_img.type, "uint8");
  const live = made.filter((t) => !t.disposed);
  assert.deepEqual(live, [m.feeds.state_img_q]);   // only the state for the next frame
});

test("the policy branch gets desire 0, right-hand traffic and its own queues; float16 models get float16 frames", async () => {
  made = [];
  const sess = session(["new_img", "desire", "traffic_convention", "state_img_q", "state_desire_q", "state_feat_q"], 1961);
  const m = new FrameModel(ort, sess, { f16: true });
  const frame = new Uint8Array(2 * 6 * 128 * 256); frame[0] = 1;
  const a = await m.run(frame), b = await m.run(frame);
  assert.equal(a.length, 1961);
  assert.deepEqual([a[0], a[2], a[3], b[3]], [0x3c00, 1, 0, 1]);   // float16 bits of 1
  assert.deepEqual(sess.feeds[0].state_feat_q.dims, [96, 1, 512]);
  assert.deepEqual([...sess.feeds[0].desire.data], new Array(8).fill(0));
  assert.equal(sess.feeds[0].state_img_q.type, "float16");
});

test("reset empties the queues (or sets given ones), release frees them and the session", async () => {
  made = [];
  const sess = session(["new_img", "state_img_q"]), m = new FrameModel(ort, sess);
  await m.run(new Uint8Array(2 * 6 * 128 * 256));
  m.reset({ state_img_q: new Uint8Array(2 * 5 * 6 * 128 * 256).fill(4) });
  assert.equal((await m.run(new Uint8Array(2 * 6 * 128 * 256)))[1], 4);
  m.reset();
  assert.equal((await m.run(new Uint8Array(2 * 6 * 128 * 256)))[1], 0);
  await m.release();
  assert.ok(sess.released && made.every((t) => t.disposed));
});

test("a failed run releases the frame and keeps the queues usable", async () => {
  made = [];
  const sess = session(["new_img", "state_img_q"]), m = new FrameModel(ort, sess);
  sess.fail = true;
  await assert.rejects(m.run(new Uint8Array(2 * 6 * 128 * 256)));
  assert.equal(sess.feeds[0].new_img.disposed, true);
  assert.equal(m.feeds.state_img_q.disposed, false);
});
