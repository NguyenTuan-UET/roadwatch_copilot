/* Hình học camera cho chạy model trên điện thoại: bản JS của các hàm Python cùng tên.
   - rotFromEuler / eulerFromRot: vendor/g01T014VinAI/common/transformations/transformations.py (euler2rot, rot2euler qua quaternion)
   - getWarpMatrix: vendor/.../transformations/model.py (khung model medmodel 512x256 fl 910, sbigmodel fl 455)
   - intrinsics, focalPxFromMm: calibration.py; wideMode, warpMatrices, coverage: model.py
   - project, egoLaneBorders, overlay: hud.py (hình làn và xe dẫn đầu để vẽ trên camera)
   Ma trận 3x3 là mảng 3 hàng; mọi phép tính bằng số thực 64 bit như numpy. Kiểm bằng
   tests/roadwatch/js/geometry.test.mjs với dữ liệu chuẩn xuất từ Python. */

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
const X_IDXS = Array.from({ length: 33 }, (_, i) => 192 * (i / 32) ** 2);
export const LANE_X_MIN = 6, LANE_X_MAX = 80, LANE_PROB = 0.4, FALLBACK_HALF_WIDTH = 1.75, CLOSE_HEADWAY_S = 1;

/** Điểm (x trước, y phải, z xuống; gốc ở camera) -> [[u, v], ...] và mảng "ở trước camera". */
export function project(camK, rpy, pts) {
  const M = matmul(matmul(camK, VIEW_FROM_DEVICE), rotFromEuler(rpy));
  const uv = [], ok = [];
  for (const p of pts) { const [a, b, c] = matvec(M, p); uv.push([a / c, b / c]); ok.push(c > 0); }
  return [uv, ok];
}

export function interp(x, xp, fp) {   // np.interp: giữ giá trị biên ngoài khoảng
  if (x <= xp[0]) return fp[0];
  if (x >= xp[xp.length - 1]) return fp[fp.length - 1];
  let i = 1; while (xp[i] < x) i++;
  return fp[i - 1] + (fp[i] - fp[i - 1]) * (x - xp[i - 1]) / (xp[i] - xp[i - 1]);
}

/** Mép trái/phải của làn mình trên lưới x (hud.ego_lane_borders). laneLines: [4][33][2] (y, z); planPos: null. */
export function egoLaneBorders(laneLines, laneProb, planPos, xEnd, height) {
  const n = 40, a = LANE_X_MIN, b = Math.max(LANE_X_MIN + 1, xEnd);
  const xs = Array.from({ length: n }, (_, i) => a + (b - a) * i / (n - 1));
  if (Math.min(...laneProb) >= LANE_PROB) {
    const col = (k, c) => xs.map((x) => interp(x, X_IDXS, laneLines[k].map((p) => p[c])));
    return [xs, [col(1, 0), col(1, 1)], [col(2, 0), col(2, 1)]];
  }
  let yc, zc;
  if (!planPos) { yc = xs.map(() => 0); zc = xs.map(() => height); }
  else {
    const px = planPos.map((p) => p[0]);
    yc = xs.map((x) => interp(x, px, planPos.map((p) => p[1])));
    zc = xs.map((x) => interp(x, px, planPos.map((p) => p[2])) + height);
  }
  return [xs, [yc.map((y) => y - FALLBACK_HALF_WIDTH), zc], [yc.map((y) => y + FALLBACK_HALF_WIDTH), zc]];
}

/** hud._layout: (mép làn, xe dẫn đầu [u, v, x] hoặc null nếu ra ngoài ảnh, close). r: kết quả của Pipeline. */
export function layout(camK, r, w, h) {
  const p = r.outputs, has = r.gap_m !== null;
  const [x, lat] = has ? [r.lead_x_m, r.lead_lat_m] : [LANE_X_MAX, 0];
  const close = has && Number.isFinite(r.ego_speed_mps) && r.ego_speed_mps > 1 && r.gap_m / r.ego_speed_mps < CLOSE_HEADWAY_S;
  const probs = [p.lane_lines_prob[3], p.lane_lines_prob[5]];   // lane_lines_prob[0, 1::2][1:3]
  const borders = egoLaneBorders(p.lane_lines, probs, p.plan || null, x, r.height_m);
  let lead = null;
  if (has) {
    const [xs, [, zl], [, zr]] = borders;
    const z = interp(x, xs, zl.map((v, i) => (v + zr[i]) / 2));
    const [[[u, v]], [ok]] = project(camK, r.rpy, [[x, lat, z]]);
    if (ok && u >= 0 && u < w && v >= 0 && v < h) lead = [u, v, x];
  }
  return [borders, lead, close];
}

const round4 = (v) => Math.round(v * 1e4) / 1e4;
/** hud.overlay: làn và xe dẫn đầu theo tỉ lệ 0..1 của ảnh, để trang vẽ trên camera. */
export function overlay(camK, r, w, h) {
  const [borders, lead, close] = layout(camK, r, w, h);
  const [xs, [yl, zl], [yr, zr]] = borders;
  const lp = project(camK, r.rpy, xs.map((x, i) => [x, yl[i], zl[i]]))[0];
  const rp = project(camK, r.rpy, xs.map((x, i) => [x, yr[i], zr[i]]))[0];
  const all = lp.concat(rp).flat();
  let lane = null;
  if (all.every(Number.isFinite) && Math.max(...all.map(Math.abs)) <= 4 * Math.max(w, h)) {
    const frac = (px) => px.filter((_, i) => i % 2 === 0).map(([u, v]) => [round4(u / w), round4(v / h)]);
    lane = { left: frac(lp), right: frac(rp) };
  }
  return { lane, lead: lead && { u: round4(lead[0] / w), v: round4(lead[1] / h), dist_m: Math.round(lead[2] * 10) / 10, close } };
}
