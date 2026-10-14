/* Hình học camera cho chạy model trên điện thoại: bản JS của các hàm Python cùng tên.
   - rotFromEuler / eulerFromRot: vendor/g01T014VinAI/common/transformations/transformations.py (euler2rot, rot2euler qua quaternion)
   - getWarpMatrix: vendor/.../transformations/model.py (khung model medmodel 512x256 fl 910, sbigmodel fl 455)
   - intrinsics, focalPxFromMm: calibration.py; wideMode, warpMatrices, coverage: model.py
   - project, egoLaneBorders, laneGeometry, LaneSmoother, overlay: hud.py (hình làn và xe dẫn đầu để vẽ trên camera;
     đường xe đi và tâm làn: lanes.mjs)
   Ma trận 3x3 là mảng 3 hàng; mọi phép tính bằng số thực 64 bit như numpy. Kiểm bằng
   tests/roadwatch/js/geometry.test.mjs với dữ liệu chuẩn xuất từ Python. */

import { EDGE_CLIP_STD, LANE_BAND, LANE_WIDTH, X_IDXS, pathReach, predictedPath, widenLane } from "./lanes.mjs";
import { arange, interp, linspace, median, polyder, polyfit, polyval } from "./num.mjs";

export const MODEL_W = 512, MODEL_H = 256;
export const WIDE_HFOV_DEG = 60;
export const EQUIV_WIDTH_MM = 34.6;
const MEDMODEL_CY = 47.6;
const MED_K = [[910, 0, 256], [0, 910, MEDMODEL_CY], [0, 0, 1]];
const SBIG_K = [[455, 0, 256], [0, 455, 0.5 * (256 + MEDMODEL_CY)], [0, 0, 1]];
// view: x phải, y xuống, z trước; device: x trước, y phải, z xuống (camera.py)
export const VIEW_FROM_DEVICE = [[0, 1, 0], [0, 0, 1], [1, 0, 0]];

export const matmul = (a, b) => a.map((row) => b[0].map((_, j) => row.reduce((s, v, k) => s + v * b[k][j], 0)));
export const matvec = (a, v) => a.map((row) => row.reduce((s, x, k) => s + x * v[k], 0));
export function inv3(m) {
  const [[a, b, c], [d, e, f], [g, h, i]] = m;
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
  const det = a * A + b * B + c * C;
  return [[A / det, -(b * i - c * h) / det, (b * f - c * e) / det],
          [B / det, (a * i - c * g) / det, -(a * f - c * d) / det],
          [C / det, -(a * h - b * g) / det, (a * e - b * d) / det]];
}

export function rotFromEuler([phi, theta, psi]) {   // Z-Y-X: Rz @ Ry @ Rx
  const cx = Math.cos(phi), sx = Math.sin(phi), cy = Math.cos(theta), sy = Math.sin(theta);
  const cz = Math.cos(psi), sz = Math.sin(psi);
  const Rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]], Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]];
  const Rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]];
  return matmul(matmul(Rz, Ry), Rx);
}

function quatFromRot(r) {
  const tr = r[0][0] + r[1][1] + r[2][2];
  let w, x, y, z, s;
  if (tr > 0) {
    s = 0.5 / Math.sqrt(tr + 1); w = 0.25 / s;
    x = (r[2][1] - r[1][2]) * s; y = (r[0][2] - r[2][0]) * s; z = (r[1][0] - r[0][1]) * s;
  } else if (r[0][0] > r[1][1] && r[0][0] > r[2][2]) {
    s = 2 * Math.sqrt(1 + r[0][0] - r[1][1] - r[2][2]);
    w = (r[2][1] - r[1][2]) / s; x = 0.25 * s; y = (r[0][1] + r[1][0]) / s; z = (r[0][2] + r[2][0]) / s;
  } else if (r[1][1] > r[2][2]) {
    s = 2 * Math.sqrt(1 + r[1][1] - r[0][0] - r[2][2]);
    w = (r[0][2] - r[2][0]) / s; x = (r[0][1] + r[1][0]) / s; y = 0.25 * s; z = (r[1][2] + r[2][1]) / s;
  } else {
    s = 2 * Math.sqrt(1 + r[2][2] - r[0][0] - r[1][1]);
    w = (r[1][0] - r[0][1]) / s; x = (r[0][2] + r[2][0]) / s; y = (r[1][2] + r[2][1]) / s; z = 0.25 * s;
  }
  return w < 0 ? [-w, -x, -y, -z] : [w, x, y, z];
}

export function eulerFromRot(r) {
  const [w, x, y, z] = quatFromRot(r);
  return [Math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)),
          Math.asin(Math.min(1, Math.max(-1, 2 * (w * y - z * x)))),
          Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))];
}

export const intrinsics = (fy, w, h) => [[fy, 0, w / 2], [0, fy, h / 2], [0, 0, 1]];
export const focalPxFromMm = (fMm, longSidePx, sensorWidthMm = null) => fMm * longSidePx / (sensorWidthMm || EQUIV_WIDTH_MM);

// calib_from_model = inv(K_model @ view_from_device) (get_view_frame_from_calib_frame(0,0,0,0)[:, :3])
const CALIB_FROM_MED = inv3(matmul(MED_K, VIEW_FROM_DEVICE));
const CALIB_FROM_SBIG = inv3(matmul(SBIG_K, VIEW_FROM_DEVICE));

/** Ma trận điểm ảnh khung model -> điểm ảnh camera (get_warp_matrix). */
export function getWarpMatrix(rpy, camK, wide = false) {
  const cameraFromCalib = matmul(matmul(camK, VIEW_FROM_DEVICE), rotFromEuler(rpy));
  return matmul(cameraFromCalib, wide ? CALIB_FROM_SBIG : CALIB_FROM_MED);
}

export function wideMode(camK, w, wide = "auto") {
  if (wide !== "auto") return wide;
  return 2 * Math.atan(w / 2 / camK[0][0]) * 180 / Math.PI > WIDE_HFOV_DEG ? "warp" : "dup";
}

/** [narrow, wide]; wide là null khi đầu vào góc rộng là ảnh hẹp nhân đôi. */
export function warpMatrices(camK, rpy, w, wide = "auto") {
  return [getWarpMatrix(rpy, camK, false), wideMode(camK, w, wide) === "warp" ? getWarpMatrix(rpy, camK, true) : null];
}

/** Tỉ lệ điểm ảnh khung model lấy mẫu được trong ảnh camera (lưới bước 4, như model.coverage). */
export function coverage(warps, w, h) {
  let worst = Infinity;
  for (const m of warps) {
    if (!m) continue;
    let inside = 0, n = 0;
    for (let y = 0; y < MODEL_H; y += 4) {
      for (let x = 0; x < MODEL_W; x += 4) {
        const sz = m[2][0] * x + m[2][1] * y + m[2][2];
        const sx = (m[0][0] * x + m[0][1] * y + m[0][2]) / sz, sy = (m[1][0] * x + m[1][1] * y + m[1][2]) / sz;
        inside += sz > 0 && sx >= 0 && sx <= w - 1 && sy >= 0 && sy <= h - 1; n++;
      }
    }
    worst = Math.min(worst, inside / n);
  }
  return worst;
}

/* ---------- HUD: làn và xe dẫn đầu (hud.py) ---------- */
export const LANE_X_MIN = 2, LANE_X_MAX = 80, LANE_PROB = 0.4, FALLBACK_HALF_WIDTH = 1.75, CLOSE_HEADWAY_S = 1;
export const LANE_MAX_WIDTH = 6, EDGE_STD_MAX = 1.5, LANE_MIN_WIDTH = 1.5, EDGE_NEAR_X = 5, LANE_PROB_OFF = 0.25;
export const MEDIAN_TICKS = 3, FIT_DEGREE = 3, TURN_AWAY = 1, LANE_END_MIN = 10, LANE_EMA = 0.25, END_EMA = 0.2, LAT_EMA = 0.35;
export const GRID = arange(LANE_X_MIN, LANE_X_MAX + 0.5, 1);   // x của hình làn trước khi cắt ở xe dẫn đầu

/** Điểm (x trước, y phải, z xuống; gốc ở camera) -> [[u, v], ...] và mảng "ở trước camera". */
export function project(camK, rpy, pts) {
  const M = matmul(matmul(camK, VIEW_FROM_DEVICE), rotFromEuler(rpy));
  const uv = [], ok = [];
  for (const p of pts) { const [a, b, c] = matvec(M, p); uv.push([a / c, b / c]); ok.push(c > 0); }
  return [uv, ok];
}

export { interp };
const at = (xs, curve, c) => xs.map((x) => interp(x, X_IDXS, curve.map((pt) => pt[c])));

/** Mép trái/phải của làn mình (hud.ego_lane_borders): [xs, [yl, zl], [yr, zr]]. Mỗi bên: vạch làn khi chắc, không thì
    mép đường bên đó khi model chắc và nó sát làn xe, không nữa thì cách bên kia một làn; không có cả hai: làn quanh
    đường đi planPos (mảng [x, y, z] từ camera, nên cộng độ cao camera) hoặc quanh trục camera. */
export function egoLaneBorders(lanes, laneProb, planPos, xEnd, height, edges = null, edgeStds = null, pair = [1, 2], n = 40) {
  const xs = linspace(LANE_X_MIN, Math.max(LANE_X_MIN + 1, xEnd), n), span = pair[1] - pair[0];
  const yCar = planPos ? interp(EDGE_NEAR_X, planPos.map((q) => q[0]), planPos.map((q) => q[1])) : 0;
  const beside = (e) => Math.abs(interp(EDGE_NEAR_X, X_IDXS, edges[e].map((q) => q[0])) - yCar) <= LANE_WIDTH * span;
  const sides = [[laneProb[0], pair[0], 0], [laneProb[1], pair[1], 1]].map(([prob, k, e]) => {
    if (prob >= LANE_PROB) return [[at(xs, lanes[k], 0), at(xs, lanes[k], 1)], false];
    if (edges && edgeStds[e][0][0] <= EDGE_STD_MAX && beside(e)) return [[at(xs, edges[e], 0), at(xs, edges[e], 1)], true];
    return [null, false];
  });
  let [[left, lEdge], [right, rEdge]] = sides;
  if (left || right) {
    if (!left) left = [right[0].map((y) => y - LANE_WIDTH * span), right[1]];
    else if (!right) right = [left[0].map((y) => y + LANE_WIDTH * span), left[1]];
    const cap = LANE_MAX_WIDTH * span;
    if (lEdge && rEdge) {
      const mid = left[0].map((y, i) => (y + right[0][i]) / 2);
      left = [left[0].map((y, i) => Math.max(y, mid[i] - cap / 2)), left[1]];
      right = [right[0].map((y, i) => Math.min(y, mid[i] + cap / 2)), right[1]];
    } else if (rEdge) right = [right[0].map((y, i) => Math.min(y, left[0][i] + cap)), right[1]];
    else if (lEdge) left = [left[0].map((y, i) => Math.max(y, right[0][i] - cap)), left[1]];
  } else {
    let yc, zc;
    if (!planPos) { yc = xs.map(() => 0); zc = xs.map(() => height); }
    else {
      const px = planPos.map((q) => q[0]);
      yc = xs.map((x) => interp(x, px, planPos.map((q) => q[1])));
      zc = xs.map((x) => interp(x, px, planPos.map((q) => q[2])) + height);
    }
    left = [yc.map((y) => y - FALLBACK_HALF_WIDTH), zc]; right = [yc.map((y) => y + FALLBACK_HALF_WIDTH), zc];
  }
  return [xs, ...insideRoad(xs, left, right, edges, edgeStds)];
}

/** Mép làn cắt ở mép đường đủ chắc (EDGE_CLIP_STD), giữ rộng ít nhất LANE_MIN_WIDTH (hud._inside_road). */
function insideRoad(xs, left, right, edges, edgeStds) {
  if (!edges || !edgeStds) return [left, right];
  let yl = left[0], yr = right[0];
  if (edgeStds[1][0][0] <= EDGE_CLIP_STD) {
    const e = at(xs, edges[1], 0);
    yr = yr.map((y, i) => Math.min(y, e[i])); yl = yl.map((y, i) => Math.min(y, yr[i] - LANE_MIN_WIDTH));
  }
  if (edgeStds[0][0][0] <= EDGE_CLIP_STD) {
    const e = at(xs, edges[0], 0);
    yl = yl.map((y, i) => Math.max(y, e[i])); yr = yr.map((y, i) => Math.max(y, yl[i] + LANE_MIN_WIDTH));
  }
  return [[yl, left[1]], [yr, right[1]]];
}

/** Đường xe sẽ đi (lanes.predictedPath) thành các điểm [x, y, 0] trên X_IDXS, hoặc null khi không có chuyển động. */
export function egoPath(p, curvature, speed, onLine = null) {
  if (curvature === null || curvature === undefined) return null;
  const ys = predictedPath(p, curvature, X_IDXS, pathReach(Number.isFinite(speed) ? speed : 0), onLine);
  return X_IDXS.map((x, i) => [x, ys[i], 0]);
}

/** x một bước lưới trước chỗ đầu tiên một đường cong quay quá TURN_AWAY hoặc nhảy; LANE_X_MAX nếu không có. */
function drawableEnd(...curves) {
  for (let i = 0; i < GRID.length - 1; i++)
    if (curves.some((c) => Math.abs(c[i + 1] - c[i]) / (GRID[i + 1] - GRID[i]) > TURN_AWAY)) return Math.max(LANE_END_MIN, GRID[Math.max(i - 1, 0)]);
  return LANE_X_MAX;
}

/** y trên GRID thành đa thức trơn, khớp tới `end`, sau đó đi thẳng theo tiếp tuyến (hud._fit). */
function fit(y, end = LANE_X_MAX) {
  const xs = GRID.filter((x) => x <= end + 1e-9), c = polyfit(xs, y.slice(0, xs.length), Math.min(FIT_DEGREE, xs.length - 1));
  const yEnd = polyval(c, end), slope = polyval(polyder(c), end);
  return GRID.map((x) => (x <= end + 1e-9 ? polyval(c, x) : yEnd + slope * (x - end)));
}

/** hud.lane_geometry: làn mình trên GRID {yl, zl, yr, zr, yc, hw, end, lat, held}. held: vạch nào được coi là chắc ở
    khung trước (giữ tới LANE_PROB_OFF). r: kết quả của Pipeline (track.mjs). */
export function laneGeometry(r, held = null) {
  const p = r.outputs, has = r.gap_m !== null && r.gap_m !== undefined;
  const path = egoPath(p, r.curvature, r.ego_speed_mps, r.straddle ?? null);
  const pair = { null: [1, 2], 1: [0, 2], 2: [1, 3] }[r.straddle ?? null];
  const edges = p.road_edges || null, stds = p.road_edges_stds || null;
  let prob = [1, 3, 5, 7].map((k) => p.lane_lines_prob[k]);
  if (held) prob = prob.map((v, k) => (held[k] && v >= LANE_PROB_OFF ? Math.max(v, LANE_PROB) : v));
  const [, [yl0, zl], [yr0, zr]] = egoLaneBorders(p.lane_lines, pair.map((k) => prob[k]), path, LANE_X_MAX, r.height_m, edges, stds, pair, GRID.length);
  const yc = path ? GRID.map((x) => interp(x, path.map((q) => q[0]), path.map((q) => q[1]))) : yl0.map((y, i) => (y + yr0[i]) / 2);
  const yl = [], yr = [], hw = [];
  yl0.forEach((_, i) => { const [a, b, c] = widenLane(yl0[i], yr0[i], yc[i], LANE_BAND * (yr0[i] - yl0[i])); yl.push(a); yr.push(b); hw.push(c); });
  const end = drawableEnd(yl, yr, yc);
  const g = Object.fromEntries(Object.entries({ yl, zl, yr, zr, yc, hw }).map(([k, v]) => [k, fit(v, end)]));
  return { ...g, end: has ? Math.min(r.lead_x_m, end) : end, lat: has ? r.lead_lat_m : null, held: prob.map((v) => v >= LANE_PROB) };
}

/** hud.LaneSmoother: một bộ mỗi lần đo; hình làn là trung vị của MEDIAN_TICKS khung gần nhất rồi làm mượt mũ. */
export class LaneSmoother {
  static CURVES = ["yl", "zl", "yr", "zr", "yc", "hw"];
  constructor() { this.geom = null; this.held = null; this.recent = []; }
  update(r) {
    const g = laneGeometry(r, this.held);
    this.held = g.held; delete g.held;
    this.recent = [...this.recent, g].slice(-MEDIAN_TICKS);
    const m = Object.fromEntries(LaneSmoother.CURVES.map((k) => [k, median(this.recent.map((x) => x[k]))]));
    m.end = median(this.recent.map((x) => x.end));
    if (!this.geom) { this.geom = { ...m, lat: g.lat }; return { ...this.geom }; }
    const s = this.geom;
    for (const k of LaneSmoother.CURVES) s[k] = s[k].map((v, i) => v + LANE_EMA * (m[k][i] - v));
    s.end += END_EMA * (m.end - s.end);
    s.lat = g.lat === null || s.lat === null ? g.lat : s.lat + LAT_EMA * (g.lat - s.lat);
    return { ...s };
  }
}

/** hud._layout: [mép làn, dải sáng [yc, zc, hw], xe dẫn đầu [u, v, x] hoặc null, close]; lane: LaneSmoother. */
export function layout(camK, r, w, h, lane = null) {
  const g = lane && lane.geom ? lane.geom : laneGeometry(r), has = r.gap_m !== null && r.gap_m !== undefined;
  const close = has && Number.isFinite(r.ego_speed_mps) && r.ego_speed_mps > 1 && r.gap_m / r.ego_speed_mps < CLOSE_HEADWAY_S;
  const xs = linspace(LANE_X_MIN, Math.max(LANE_X_MIN + 1, g.end), 40);
  const [yl, zl, yr, zr, yc, hw] = ["yl", "zl", "yr", "zr", "yc", "hw"].map((k) => xs.map((x) => interp(x, GRID, g[k])));
  const zm = zl.map((z, i) => (z + zr[i]) / 2);
  const band = [yc.map((y, i) => Math.min(Math.max(y, yl[i] + hw[i]), yr[i] - hw[i])), zm, hw];
  let lead = null;
  if (has) {
    const x = r.lead_x_m, lat = g.lat === null ? r.lead_lat_m : g.lat, z = interp(x, xs, zm);
    const [[[u, v]], [ok]] = project(camK, r.rpy, [[x, lat, z]]);
    if (ok && u >= 0 && u < w && v >= 0 && v < h) lead = [u, v, x];
  }
  return [[xs, [yl, zl], [yr, zr]], band, lead, close];
}

/** Chỉ số mẫu gần nhất mà từ đó cả hai mép chiếu ra hữu hạn và trong 4 lần cỡ ảnh, hoặc null nếu còn dưới 2 mẫu. */
function firstOnPicture(lp, rp, w, h) {
  let i0 = 0;
  lp.forEach((a, i) => {
    const q = [...a, ...rp[i]];
    if (!q.every(Number.isFinite) || Math.max(...q.map(Math.abs)) > 4 * Math.max(w, h)) i0 = i + 1;
  });
  return lp.length - i0 >= 2 ? i0 : null;
}

const round4 = (v) => Math.round(v * 1e4) / 1e4;
/** hud.overlay: làn, dải đường đi và xe dẫn đầu theo tỉ lệ 0..1 của ảnh, để trang vẽ trên camera. */
export function overlay(camK, r, w, h, lane = null) {
  const [[xs, [yl, zl], [yr, zr]], [yc, zc, hw], lead, close] = layout(camK, r, w, h, lane);
  const band = (left, right) => {
    const [lp] = project(camK, r.rpy, xs.map((x, i) => [x, left[0][i], left[1][i]]));
    const [rp] = project(camK, r.rpy, xs.map((x, i) => [x, right[0][i], right[1][i]]));
    const i0 = firstOnPicture(lp, rp, w, h);
    if (i0 === null) return null;
    const frac = (px) => px.slice(i0).filter((_, i) => i % 2 === 0).map(([u, v]) => [round4(u / w), round4(v / h)]);
    return { left: frac(lp), right: frac(rp) };
  };
  const path = r.curvature === null || r.curvature === undefined ? null
    : band([yc.map((y, i) => y - hw[i]), zc], [yc.map((y, i) => y + hw[i]), zc]);
  return { lane: band([yl, zl], [yr, zr]), path,
           lead: lead && { u: round4(lead[0] / w), v: round4(lead[1] / h), dist_m: Math.round(lead[2] * 10) / 10, close } };
}
