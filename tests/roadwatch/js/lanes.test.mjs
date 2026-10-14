import { test } from "node:test";
import assert from "node:assert/strict";
import { close, floats, golden } from "./golden.mjs";
import { parseOutputs } from "../../../src/roadwatch/ui/onphone/parse.mjs";
import { X_IDXS, laneCenter, pathReach, predictedPath, straddle } from "../../../src/roadwatch/ui/onphone/lanes.mjs";
import { laneGeometry } from "../../../src/roadwatch/ui/onphone/geometry.mjs";

const tol = { atol: 1e-4, rtol: 1e-4 };   // Python reads float32 outputs in float32; here float64

test("lane functions of pipeline.py and hud.lane_geometry on real outputs, also when the car drives on a line", () => {
  const g = golden("lanes");
  g.cases.forEach((c, i) => {
    const p = parseOutputs(floats(c.raw)), at = `case ${i}`;
    for (const prev of [null, 1, 2]) assert.equal(straddle(p, prev), c.straddle[String(prev === null ? "None" : prev)], `${at} straddle(${prev})`);
    const on = c.straddle.None, reach = pathReach(c.speed);
    const [y, half, ref] = laneCenter(p, c.curv, c.lx, reach, on);
    assert.equal(ref, c.center[2], `${at} lane_ref`);
    close([y, half], c.center.slice(0, 2), tol, `${at} lane_center`);
    close(predictedPath(p, c.curv, X_IDXS, reach, on), c.path, tol, `${at} predicted_path`);
    const r = { outputs: p, gap_m: c.gap, curvature: c.curv, ego_speed_mps: c.speed, straddle: on, height_m: 1.3, lead_x_m: 40, lead_lat_m: 0.4 };
    const geom = laneGeometry(r);
    for (const k of ["yl", "zl", "yr", "zr", "yc", "hw"]) close(geom[k], c.geom[k], { atol: 1e-3, rtol: 1e-4 }, `${at} geom.${k}`);
    close(geom.end, c.geom.end, tol, `${at} geom.end`);
    assert.equal(geom.lat, c.geom.lat, `${at} geom.lat`);
    assert.deepEqual(geom.held.map(Number), c.geom.held, `${at} geom.held`);
  });
});
