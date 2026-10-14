import { test } from "node:test";
import assert from "node:assert/strict";
import { close, floats, golden } from "./golden.mjs";
import { parseOutputs } from "../../../src/roadwatch/ui/onphone/parse.mjs";
import { Pipeline, pyFixed } from "../../../src/roadwatch/ui/onphone/track.mjs";
import { LaneSmoother, overlay } from "../../../src/roadwatch/ui/onphone/geometry.mjs";

test("Python-style rounding", () => {
  assert.equal(pyFixed(2.5, 0), "2"); assert.equal(pyFixed(3.5, 0), "4"); assert.equal(pyFixed(0.25, 1), "0.2");
  assert.equal(pyFixed(-2.5, 0), "-2"); assert.equal(pyFixed(1.2345, 2), "1.23"); assert.equal(pyFixed(99.6, 0), "100");
});

/* Mỗi khung: Result như pipeline.Pipeline.step; mỗi 10 khung: hud.overlay không làm mượt và với LaneSmoother (job.py
   cập nhật nó mỗi khung và gửi bản làm mượt cho điện thoại), và hình làn đã làm mượt. */
function replay(name) {
  const g = golden(name), raws = floats(g.raws), n = g.n;
  const pipe = new Pipeline({ w: g.w, h: g.h, fy: g.fy, dCamBumper: g.d }), lane = new LaneSmoother();
  const tol = { atol: 1e-4, rtol: 1e-4 };   // Python reads float32 outputs in float32; here float64
  const sameOverlay = (o, want, at) => {
    for (const k of ["lane", "path"]) {
      if (want[k]) { close(o[k].left, want[k].left, { atol: 2e-4 }, `${at} ${k}.left`); close(o[k].right, want[k].right, { atol: 2e-4 }, `${at} ${k}.right`); }
      else assert.equal(o[k], null, `${at} ${k}`);
    }
    if (want.lead) {
      close([o.lead.u, o.lead.v, o.lead.dist_m], [want.lead.u, want.lead.v, want.lead.dist_m], { atol: 2e-4 }, `${at} lead`);
      assert.equal(o.lead.close, want.lead.close, at);
    } else assert.equal(o.lead, null, at);
  };
  g.rows.forEach((want, i) => {
    const r = pipe.update(parseOutputs(raws.subarray(i * n, (i + 1) * n)), want.pts, want.vgps ?? NaN), at = `${name} tick ${i}`;
    assert.equal(r.status, want.status, at);
    for (const k of ["rpy", "rpy_est", "height_m", "ego_speed_mps", "lead_prob", "gap_m", "lead_speed_mps", "ttc_s", "gap_std_m",
                     "lead_lat_m", "lead_x_m", "lead_raw_m", "gps_speed_mps", "gap_pred_m", "model_speed_mps", "curvature"])
      close(r[k], want[k], tol, `${at} ${k}`);
    assert.equal(r.lane_ref, want.lane_ref, `${at} lane_ref`);
    assert.equal(r.straddle, want.straddle, `${at} straddle`);
    close(pipe.coverage, want.coverage, { atol: 1e-12 }, `${at} coverage`);
    lane.update(r);
    if (want.overlay) {
      sameOverlay(overlay(pipe.K, r, g.w, g.h), want.overlay, `${at} overlay`);
      sameOverlay(overlay(pipe.K, r, g.w, g.h, lane), want.overlay_lane, `${at} overlay (smoothed)`);
      for (const k of ["yl", "zl", "yr", "zr", "yc", "hw"]) close(lane.geom[k], want.lane[k], { atol: 1e-3, rtol: 1e-4 }, `${at} lane.${k}`);
      close([lane.geom.end, lane.geom.lat], [want.lane.end, want.lane.lat], tol, `${at} lane end, lat`);
    }
  });
}

test("20 s of comma2k19 (highway) replayed from the model's raw outputs: every Result and the HUD as Python", () => replay("pipeline"));
test("15 s of a curve without lane lines (comma2k19 lane_c02: ego path, road edges): as Python", () => replay("pipeline_c02"));

test("a slower tick (phone below 20 Hz) rescales the model's velocities and the Kalman step, as tick() does for videos", () => {
  const g = golden("pipeline"), raws = floats(g.raws), n = g.n;
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
