import { test } from "node:test";
import assert from "node:assert/strict";
import { close, floats, golden } from "./golden.mjs";
import { parseOutputs } from "../../../src/roadwatch/ui/onphone/parse.mjs";
import { Pipeline, pyFixed } from "../../../src/roadwatch/ui/onphone/track.mjs";
import { overlay } from "../../../src/roadwatch/ui/onphone/geometry.mjs";

test("Python-style rounding", () => {
  assert.equal(pyFixed(2.5, 0), "2"); assert.equal(pyFixed(3.5, 0), "4"); assert.equal(pyFixed(0.25, 1), "0.2");
  assert.equal(pyFixed(-2.5, 0), "-2"); assert.equal(pyFixed(1.2345, 2), "1.23"); assert.equal(pyFixed(99.6, 0), "100");
});

test("20 s of comma2k19 replayed from the model's raw outputs: every Result as pipeline.Pipeline.step", () => {
  const g = golden("pipeline"), raws = floats(g.raws), n = 707;
  const pipe = new Pipeline({ w: g.w, h: g.h, fy: g.fy, dCamBumper: g.d });
  const tol = { atol: 1e-4, rtol: 1e-4 };   // Python reads float32 outputs in float32; here float64
  g.rows.forEach((want, i) => {
    const r = pipe.update(parseOutputs(raws.subarray(i * n, (i + 1) * n)), want.pts, want.vgps ?? NaN), at = `tick ${i}`;
    assert.equal(r.status, want.status, at);
    for (const k of ["rpy", "rpy_est", "height_m", "ego_speed_mps", "lead_prob", "gap_m", "lead_speed_mps", "ttc_s", "gap_std_m",
                     "lead_lat_m", "lead_x_m", "lead_raw_m", "gps_speed_mps", "gap_pred_m", "model_speed_mps"])
      close(r[k], want[k], tol, `${at} ${k}`);
    close(pipe.coverage, want.coverage, { atol: 1e-12 }, `${at} coverage`);
    if (want.overlay) {
      const o = overlay(pipe.K, r, g.w, g.h);
      if (want.overlay.lane) { close(o.lane.left, want.overlay.lane.left, { atol: 2e-4 }, `${at} lane.left`); close(o.lane.right, want.overlay.lane.right, { atol: 2e-4 }, `${at} lane.right`); }
      else assert.equal(o.lane, null, at);
      if (want.overlay.lead) close([o.lead.u, o.lead.v, o.lead.dist_m], [want.overlay.lead.u, want.overlay.lead.v, want.overlay.lead.dist_m], { atol: 2e-4 }, `${at} lead`);
      else assert.equal(o.lead, null, at);
      if (want.overlay.lead) assert.equal(o.lead.close, want.overlay.lead.close, at);
    }
  });
});

test("a slower tick (phone below 20 Hz) rescales the model's velocities and the Kalman step, as tick() does for videos", () => {
  const g = golden("pipeline"), raws = floats(g.raws), n = 707;
  const at20 = new Pipeline({ w: g.w, h: g.h, fy: g.fy, dCamBumper: g.d });
  const slow = new Pipeline({ w: g.w, h: g.h, fy: g.fy, dCamBumper: g.d });
  let a, b;
  for (let i = 0; i < 120; i++) {
    const p = parseOutputs(raws.subarray(i * n, (i + 1) * n));
    a = at20.update(p, i * 0.05);
    b = slow.update(p, i * 0.15, NaN, 0.15);   // same model outputs, frames 150 ms apart
  }
  close(b.model_speed_mps, a.model_speed_mps / 3, { atol: 1e-9, rtol: 1e-9 }, "ego speed from the model / 3");
  assert.equal(slow.tracker.lostT, 0);
  close(slow.vel_scale, 1 / 3, {}, "vel_scale");
});
