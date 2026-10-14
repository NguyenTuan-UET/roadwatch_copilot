/* Làn của xe mình và đường xe sẽ đi, bản JS của các hàm cùng tên trong pipeline.py (BT-A chọn xe dẫn đầu trong làn,
   hud.py vẽ làn): straddle, path_reach, path_offset, plan_offset, road_bounds, _on_road, ego_offset,
   lane_lines_center, widen_lane, lane_center, predicted_path. Hằng số như pipeline.py.
   p: đầu ra đã đọc của model (parse.mjs), không có chiều batch: Python outputs['lane_lines'][0] là JS p.lane_lines;
   lane_lines_prob[0, 1::2] là p.lane_lines_prob[1], [3], [5], [7]. Model không có road_edges / plan (bản cũ 707 số):
   như Python khi thiếu head đó. x là một số; hàm nhận mảng có tên ...At. Kiểm ở tests/roadwatch/js/lanes.test.mjs
   và track.test.mjs với dữ liệu chuẩn xuất từ Python. */
import { interp } from "./num.mjs";

export const X_IDXS = Array.from({ length: 33 }, (_, i) => 192 * (i / 32) ** 2);
export const MAX_LAT_M = 2.0, LANE_WIDTH = 3.5, LANE_BAND = 0.27, BAND_MARGIN = 0.3, NEAR_FROM_YAW = true, WIDEN_LEAD = true;
export const LANE_PROB = 0.4, CURV_EMA = 0.08, CURV_MAX = 0.1, A_LAT_MAX = 4.0, CURV_MIN_SPEED = 2.0, STRADDLE_X_M = 5.0;
export const HEADING_MAX = 0.6, PLAN_MIN_M = 5.0, EDGE_CLIP_STD = 3.0, EDGE_MARGIN_M = 0.9;
export const STRADDLE_ON_M = 0.6, STRADDLE_OFF_M = 0.9, PATH_REACH_S = 1.5, PATH_REACH_MIN_M = 15;

const col = (curve, c) => curve.map((pt) => pt[c]);   // [33][2] -> 33 số của cột c
const lineProb = (p, k) => p.lane_lines_prob[2 * k + 1];   // lane_lines_prob[0, 1::2][k]

export const curvatureMax = (speed) => Math.min(CURV_MAX, A_LAT_MAX / Math.max(speed, 1e-3) ** 2);

/** Vạch làn xe đang đè (1 trái, 2 phải) hoặc null; giữ vạch cũ tới khi cách xa hơn STRADDLE_OFF_M. */
export function straddle(p, prev = null) {
  if (!p.lane_lines || !p.lane_lines_prob) return null;
  const near = new Map();
  for (const k of [1, 2]) if (lineProb(p, k) >= LANE_PROB) near.set(k, Math.abs(interp(STRADDLE_X_M, X_IDXS, col(p.lane_lines[k], 0))));
  if (prev !== null && near.has(prev) && near.get(prev) <= STRADDLE_OFF_M) return prev;
  let best = null;
  for (const [k, d] of near) if (d < STRADDLE_ON_M && (best === null || d < near.get(best))) best = k;
  return best;
}

export const pathReach = (speed) => Math.max(PATH_REACH_MIN_M, speed * PATH_REACH_S);

export function pathOffset(curvature, x, reach) {
  if (curvature) reach = Math.min(reach, HEADING_MAX / Math.abs(curvature));
  const xa = Math.min(x, reach);
  return curvature * xa * (x - xa / 2);
}

/** Đường model tự đi (head plan), đã giới hạn góc quay; trả về hàm x -> y, hoặc null khi không có / quá ngắn. */
function planCurve(p) {
  if (!p.plan) return null;
  let px = p.plan.map((r) => r[0]), py = p.plan.map((r) => r[1]);
  const keep = [];
  let run = -Infinity;
  for (let i = 0; i < px.length; i++) {
    run = Math.max(run, px[i]);
    keep.push((i === 0 || px[i] - px[i - 1] > 0.05) && px[i] >= run);
  }
  px = px.filter((_, i) => keep[i]); py = py.filter((_, i) => keep[i]);
  if (px.length < 3 || px[px.length - 1] < PLAN_MIN_M) return null;
  const k = Math.tan(HEADING_MAX), slopes = [], ys = [py[0]];
  for (let i = 1; i < px.length; i++) {
    slopes.push(Math.min(k, Math.max(-k, (py[i] - py[i - 1]) / (px[i] - px[i - 1]))));
    ys.push(ys[i - 1] + slopes[i - 1] * (px[i] - px[i - 1]));
  }
  const xEnd = px[px.length - 1], yEnd = ys[ys.length - 1], sEnd = slopes[slopes.length - 1];
  return (x) => (x <= xEnd ? interp(x, px, ys) : yEnd + sEnd * (x - xEnd));
}

export function planOffset(p, x) { const f = planCurve(p); return f && f(x); }

/** [trái, phải]: y của mép đường ở x khi đủ chắc (std gần xe <= EDGE_CLIP_STD), null cho bên không chắc. */
export function roadBounds(p, x) {
  if (!p.road_edges || !p.road_edges_stds) return [null, null];
  return [0, 1].map((k) => (p.road_edges_stds[k][0][0] <= EDGE_CLIP_STD ? interp(x, X_IDXS, col(p.road_edges[k], 0)) : null));
}

export function onRoad(p, x, y) {
  const [left, right] = roadBounds(p, x);
  if (left === null && right === null) return y;
  let lo = left === null ? -Infinity : left + EDGE_MARGIN_M, hi = right === null ? Infinity : right - EDGE_MARGIN_M;
  if (left !== null && right !== null) { const mid = (lo + hi) / 2; lo = Math.min(lo, mid); hi = Math.max(hi, mid); }
  return Math.min(Math.max(y, lo), hi);
}

export function laneLinesCenter(p, x, onLine = null) {
  if (!p.lane_lines || !p.lane_lines_prob) return null;
  if (onLine !== null) return interp(x, X_IDXS, col(p.lane_lines[onLine], 0));
  if (Math.min(lineProb(p, 1), lineProb(p, 2)) < LANE_PROB) return null;
  return (interp(x, X_IDXS, col(p.lane_lines[1], 0)) + interp(x, X_IDXS, col(p.lane_lines[2], 0))) / 2;
}

export function egoOffset(p, curvature, x, reach) {
  const y = pathOffset(curvature, x, reach), plan = planCurve(p);
  if (!NEAR_FROM_YAW || laneLinesCenter(p, 20) !== null) return plan ? plan(x) : y;
  if (!plan) return y;
  const xr = curvature ? Math.min(reach, HEADING_MAX / Math.abs(curvature)) : reach;
  const p0 = plan(xr - 0.5), p1 = plan(xr), p2 = plan(xr + 0.5);
  return y + (x > xr ? plan(x) - p1 - (p2 - p0) * (x - xr) : 0);
}

/** Mép làn [yl, yr] nới ra để phủ đường đi ở yc (dải sáng nửa rộng hw), tối đa hai làn; trả về [yl, yr, hw]. */
export function widenLane(yl, yr, yc, hw) {
  yl = Math.max(Math.min(yl, yc - hw - BAND_MARGIN), yr - 2 * LANE_WIDTH);
  yr = Math.min(Math.max(yr, yc + hw + BAND_MARGIN), yl + 2 * LANE_WIDTH);
  return [yl, yr, hw];
}

/** [tâm làn ở x, nửa rộng cửa sổ tìm xe dẫn đầu, nguồn: "lane_lines" | "both_lanes" | "ego_path"]. */
export function laneCenter(p, curvature, x, reach, onLine = null) {
  const c = laneLinesCenter(p, x, onLine);
  if (c === null) return [onRoad(p, x, egoOffset(p, curvature, x, reach)), MAX_LAT_M, "ego_path"];
  const plan = onLine === null && WIDEN_LEAD ? planOffset(p, x) : null;
  if (plan !== null) {
    const yl = laneLinesCenter(p, x, 1), yr = laneLinesCenter(p, x, 2);
    const [wl, wr] = widenLane(yl, yr, onRoad(p, x, plan), LANE_BAND * (yr - yl));
    if (wl < yl - 1e-6 || wr > yr + 1e-6) return [(wl + wr) / 2, (wr - wl) / 2 + 0.2, "both_lanes"];
  }
  return [c, MAX_LAT_M, "lane_lines"];
}

/** y của đường xe sẽ đi tại từng x của xs: từ xe vào dần tâm làn trong `reach` mét, luôn trên mặt đường. */
export function predictedPath(p, curvature, xs, reach, onLine = null) {
  return xs.map((x) => {
    let ego = egoOffset(p, curvature, x, reach);
    const c = laneLinesCenter(p, x, onLine);
    if (c !== null) { const w = Math.min(1, Math.max(0, x / reach)); ego += w * w * (3 - 2 * w) * (c - ego); }
    return onRoad(p, x, ego);
  });
}
