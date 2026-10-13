import test from "node:test";
import assert from "node:assert/strict";
import { inferFrame } from "../../../src/roadwatch/ui/onphone/inference.mjs";

function tensor(data = []) {
  return { data, disposed: false, dispose() { assert.equal(this.disposed, false); this.disposed = true; } };
}

test("each frame releases the previous state and all outputs except the next state", async () => {
  const image = tensor(), oldState = tensor(), output = tensor([1, 2]), nextState = tensor();
  const session = { run: async () => ({ outputs: output, next_state_img_q: nextState }) };
  const result = await inferFrame(session, image, oldState, (data) => [...data]);
  assert.deepEqual(result.parsed, [1, 2]);
  assert.equal(result.nextState, nextState);
  assert.equal(image.disposed, true);
  assert.equal(oldState.disposed, true);
  assert.equal(output.disposed, true);
  assert.equal(nextState.disposed, false);
});

test("a failed run releases both inputs", async () => {
  const image = tensor(), oldState = tensor();
  await assert.rejects(inferFrame({ run: async () => { throw new Error("run failed"); } }, image, oldState, () => {}));
  assert.equal(image.disposed, true);
  assert.equal(oldState.disposed, true);
});

test("a failed parse also releases the new state", async () => {
  const image = tensor(), oldState = tensor(), output = tensor([1]), nextState = tensor();
  await assert.rejects(inferFrame({ run: async () => ({ outputs: output, next_state_img_q: nextState }) },
    image, oldState, () => { throw new Error("parse failed"); }));
  for (const value of [image, oldState, output, nextState]) assert.equal(value.disposed, true);
});
