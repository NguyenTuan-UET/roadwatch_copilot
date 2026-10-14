import { test } from "node:test";
import { close, golden } from "./golden.mjs";
import { parseOutputs } from "../../../src/roadwatch/ui/onphone/parse.mjs";

test("model outputs read as Parser (float32 there)", () => {
  const g = golden("parse"), p = parseOutputs(Float32Array.from(g.raw));
  for (const [k, want] of Object.entries(g.parsed)) close(p[k], want, { atol: 1e-6, rtol: 1e-5 }, k);
});
