import { test } from "node:test";
import assert from "node:assert/strict";
import { close, golden } from "./golden.mjs";
import { coverage, eulerFromRot, focalPxFromMm, intrinsics, project, rotFromEuler, warpMatrices, wideMode } from "../../../src/roadwatch/ui/onphone/geometry.mjs";

const g = golden("geometry");

test("euler <-> rotation as transformations.py", () => {
  for (const { e, rot, back } of g.euler) { close(rotFromEuler(e), rot, {}, "rot"); close(eulerFromRot(rotFromEuler(e)), back, { atol: 1e-12 }, "back"); }
  for (const { f_mm, px, fy } of g.focal) close(focalPxFromMm(f_mm, px), fy);
});

test("warp matrices, wide mode, coverage and projection as model.py / hud.py", () => {
  for (const c of g.cases) {
    const k = intrinsics(c.fy, c.w, c.h), ws = warpMatrices(k, c.rpy, c.w, c.wide), tag = `${c.w}x${c.h} ${c.rpy}`;
    close(k, c.K, {}, `${tag} K`);
    close(ws[0], c.narrow, { atol: 1e-9, rtol: 1e-12 }, `${tag} narrow`);
    assert.equal(wideMode(k, c.w, c.wide), c.mode, tag);
    if (c.wide_m) close(ws[1], c.wide_m, { atol: 1e-9, rtol: 1e-12 }, `${tag} wide`); else assert.equal(ws[1], null);
    assert.equal(coverage(ws, c.w, c.h), c.coverage, `${tag} coverage`);
    const [uv, ok] = project(k, c.rpy, c.pts);
    close(uv, c.uv, { atol: 1e-7 }, `${tag} uv`); assert.deepEqual(ok, c.ok);
  }
});
