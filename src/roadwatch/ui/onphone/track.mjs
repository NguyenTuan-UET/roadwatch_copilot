/* Phần sau model của BT-A cho chạy trên điện thoại, bản JS của:
   - calibration.AutoCalib (góc lắp camera từ road_transform và hướng chuyển động);
   - pipeline.LeadTracker (Kalman vận tốc không đổi), temporal.MotionEstimator (khớp đường thẳng trên lịch sử);
   - pipeline.Pipeline.step, trừ phần chạy model: trang nắn ảnh bằng pipeline.warps, chạy model, đọc đầu ra (parse.mjs)
     rồi gọi update(); thứ tự như Python (góc mới chỉ dùng từ khung sau). Chưa có FocalFromSpeed (tự chỉnh tiêu cự).
   Hàm thuần: thời gian là pts của khung, không đọc đồng hồ hệ thống. Kiểm ở tests/roadwatch/js/track.test.mjs bằng
   một chuỗi khung thật xuất từ Python. */
import { coverage, eulerFromRot, intrinsics, matmul, rotFromEuler, warpMatrices } from "./geometry.mjs";

export const MODEL_DT = 1 / 20;
export const MIN_COVERAGE = 0.95, LEAD_PROB = 0.5, MAX_LAT_M = 2.0, EGO_EMA = 0.15, TTC_MAX_S = 10.0, PREDICT_S = 1.0;
const rad = (d) => d * Math.PI / 180;

/** Định dạng như Python f"{x:.{d}f}": làm tròn nửa về số chẵn khi đúng giữa (toFixed làm tròn lên). */
export function pyFixed(x, d) {
  const neg = x < 0, a = Math.abs(x), scaled = a * 10 ** d, fl = Math.floor(scaled);
  let s = a.toFixed(d);
  if (scaled - fl === 0.5 && Number.isInteger(a * 1024)) s = ((fl % 2 === 0 ? fl : fl + 1) / 10 ** d).toFixed(d);
  return (neg && Number(s) !== 0 ? "-" : "") + s;
}

export class AutoCalib {
  static MIN_SPEED = 5.0;
  static MAX_YAW_RATE = rad(3);
  static MAX_ROAD_STD = rad(1.5);
  static LIMIT = rad(20);
  static SETTLED_SAMPLES = 40;
  static MIN_ALPHA = 0.01;

  constructor({ rpy0 = null, usePitch = true, useRoll = true, useRoad = true } = {}) {
    this.est = rpy0 ? [...rpy0] : [0, 0, 0];
    this.mask = [useRoll ? 1 : 0, usePitch ? 1 : 0, 1];
    this.useRoad = useRoad;
    this.warp_rpy = this.rpy;
    this.n = 0;
  }
  get rpy() { return this.est.map((v, i) => v * this.mask[i]); }
  get settled() { return this.n >= AutoCalib.SETTLED_SAMPLES; }
  _fold(observed, axes) {
    const now = eulerFromRot(matmul(rotFromEuler(this.warp_rpy), rotFromEuler(observed)));
    const alpha = Math.max(1 / (this.n + 2), AutoCalib.MIN_ALPHA);
    for (const k of axes) this.est[k] += alpha * (now[k] - this.est[k]);
    this.est = this.est.map((v) => Math.min(AutoCalib.LIMIT, Math.max(-AutoCalib.LIMIT, v)));
  }
  /** pose: [tx, ty, tz, rx, ry, rz] (m/s, rad/s); trả về true nếu khung được dùng. */
  update(pose, roadTransform = null, roadTransformStd = null) {
    let used = false;
    if (this.useRoad && roadTransform && (!roadTransformStd || Math.max(...roadTransformStd.slice(3)) < AutoCalib.MAX_ROAD_STD)) {
      this._fold(roadTransform.slice(3), [0, 1, 2]); used = true;
    }
    const [tx, ty, tz, , , rz] = pose;
    if (tx >= AutoCalib.MIN_SPEED && Math.abs(rz) <= AutoCalib.MAX_YAW_RATE) {
      this._fold([0, -Math.atan2(tz, tx), Math.atan2(ty, tx)], [1, 2]); used = true;
    }
    this.n += used;
    return used;
  }
}

/** Kalman vận tốc không đổi trên khoảng cách xe dẫn đầu (pipeline.LeadTracker). */
export class LeadTracker {
  static LOST_AFTER_S = 0.5;
  constructor(accelStd = 3.0) { this.q = accelStd ** 2; this.x = null; this.P = null; this.lostT = 0; }
  _restart(meas, r) { this.x = [meas, 0]; this.P = [[r, 0], [0, 25]]; }
  update(dt, meas, measStd) {
    if (meas === null) {
      this.lostT += dt;
      if (this.lostT > LeadTracker.LOST_AFTER_S) this.x = null;
      return this.x;
    }
    this.lostT = 0;
    const r = Math.max(measStd, 0.5) ** 2;
    if (this.x === null) { this._restart(meas, r); return this.x; }
    const [x0, x1] = this.x, P = this.P;
    this.x = [x0 + dt * x1, x1];
    const q = this.q, P00 = P[0][0] + dt * (P[1][0] + P[0][1]) + dt * dt * P[1][1], P01 = P[0][1] + dt * P[1][1];
    const P10 = P[1][0] + dt * P[1][1], P11 = P[1][1];
    this.P = [[P00 + q * dt ** 4 / 4, P01 + q * dt ** 3 / 2], [P10 + q * dt ** 3 / 2, P11 + q * dt ** 2]];
    const innov = meas - this.x[0];
    if (Math.abs(innov) > Math.max(8, 0.3 * meas)) { this._restart(meas, r); return this.x; }
    const S = this.P[0][0] + r, k = [this.P[0][0] / S, this.P[1][0] / S];
    this.x = [this.x[0] + k[0] * innov, this.x[1] + k[1] * innov];
    const row = this.P[0];
    this.P = [[this.P[0][0] - k[0] * row[0], this.P[0][1] - k[0] * row[1]], [this.P[1][0] - k[1] * row[0], this.P[1][1] - k[1] * row[1]]];
    return this.x;
  }
}

/* temporal.MotionEstimator: khớp đường thẳng có trọng số trên lịch sử khoảng cách */
export const WINDOW_S = 2.0, MIN_SAMPLES = 5, MAX_GAP_S = 0.5, JUMP_M = 8, RATE_STD_FLOOR = 0.3, RAMP_SAMPLES = 20;
export class Motion {
  constructor(dist, rate, rateStd, t, n = 0) { Object.assign(this, { dist, rate, rate_std: rateStd, t, n }); }
  get weight() { return Math.min(1, (this.n - MIN_SAMPLES + 1) / RAMP_SAMPLES); }
  predict(h) { return Math.max(0, this.dist + this.rate * h); }
}
function lineFit(x, d, w) {
  let sw = 0, sx = 0, sxx = 0, sxd = 0, sd = 0;
  for (let i = 0; i < x.length; i++) { sw += w[i]; sx += w[i] * x[i]; sxx += w[i] * x[i] * x[i]; sxd += w[i] * x[i] * d[i]; sd += w[i] * d[i]; }
  const den = sw * sxx - sx * sx;
  if (den <= 1e-9) return null;
  return [(sxx * sd - sx * sxd) / den, (sw * sxd - sx * sd) / den, Math.sqrt(sw / den)];
}
export class MotionEstimator {
  constructor(windowS = WINDOW_S) { this.windowS = windowS; this.hist = []; this.last = null; }
  reset() { this.hist = []; this.last = null; }
  coast(t) {
    if (!this.last || !this.hist.length || t - this.hist[this.hist.length - 1][0] > MAX_GAP_S) return null;
    const l = this.last;
    return new Motion(l.dist + l.rate * (t - l.t), l.rate, l.rate_std, t, l.n);
  }
  update(t, dist, std) {
    if (this.hist.length) {
      const [t0, d0] = this.hist[this.hist.length - 1];
      if (t - t0 > MAX_GAP_S || Math.abs(dist - d0) > Math.max(JUMP_M, 0.3 * dist)) this.reset();
    }
    this.hist.push([t, dist, Math.max(std, 0.5)]);
    while (this.hist[0][0] < t - this.windowS) this.hist.shift();
    if (this.hist.length < MIN_SAMPLES) return null;
    const fit = lineFit(this.hist.map((h) => h[0] - t), this.hist.map((h) => h[1]), this.hist.map((h) => 1 / h[2] ** 2));
    if (!fit) return null;
    this.last = new Motion(fit[0], fit[1], Math.max(fit[2], RATE_STD_FLOOR), t, this.hist.length);
    return this.last;
  }
}

function insertSorted(arr, v) {   // giữ mảng tăng dần: trung vị độ cao camera như np.median trên mọi khung
  let lo = 0, hi = arr.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (arr[mid] < v) lo = mid + 1; else hi = mid; }
  arr.splice(lo, 0, v);
}
const median = (s) => (s.length % 2 ? s[s.length >> 1] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2);

/** pipeline.Pipeline không có model: update(p, pts, vGps) sau mỗi lần chạy model trên pipeline.warps. */
export class Pipeline {
  constructor({ w, h, fy, dCamBumper, tickDt = MODEL_DT, usePitch = true, wide = "auto", temporal = true }) {
    Object.assign(this, { w, h, d_cam_bumper: dCamBumper, wide, tick_dt: tickDt, vel_scale: MODEL_DT / tickDt });
    this.K = intrinsics(fy, w, h);
    this.cal = new AutoCalib({ usePitch });
    this.tracker = new LeadTracker();
    this.motion = new MotionEstimator(); this.temporal = temporal;
    this.n = 0;
    this._rewarp(this.cal.rpy);
    this.heights = [];
    this.v_ego = 0; this.gap_std = null; this.lat = null; this.v_lead = null; this.v_model = 0;
  }
  _rewarp(rpy) {
    this.rpy = [...rpy];
    this.warps = warpMatrices(this.K, this.rpy, this.w, this.wide);
    this.coverage = coverage(this.warps, this.w, this.h);
    this.cal.warp_rpy = this.rpy;
  }
  get settled() { return this.cal.settled; }

  /** p: đầu ra đã đọc của khung vừa chạy; pts: giờ của khung (giây); vGps: tốc độ GPS (m/s) hoặc NaN.
      dt: khoảng thời gian thật từ khung trước (giây). Python dùng một tick_dt cố định cho cả video; trên điện thoại nhịp
      khung đổi theo tải máy, nên vận tốc của model (học ở 50 ms/khung) và bước Kalman theo dt thật. Không truyền = như Python. */
  update(p, pts, vGps = NaN, dt = null) {
    if (dt !== null && dt > 0) { this.tick_dt = dt; this.vel_scale = MODEL_DT / dt; }
    this.n += 1;
    const pose = p.pose.map((v) => v * this.vel_scale);
    if (this.cal.update(pose, p.road_transform, p.road_transform_stds)) this._rewarp(this.cal.rpy);
    insertSorted(this.heights, p.road_transform[2]);
    const [lx, ly, vLead] = p.lead[0][0];
    const lstd = p.lead_stds[0][0][0], prob = p.lead_prob[0];
    const has = this.settled && prob >= LEAD_PROB && Math.abs(ly) <= MAX_LAT_M && lx > 0;
    const xf = this.tracker.update(this.tick_dt, has ? lx : null, lstd);
    let mot = null;
    if (this.temporal) mot = has ? this.motion.update(pts, lx, lstd) : this.motion.coast(pts);
    if (has) { this.gap_std = lstd; this.lat = ly; this.v_lead = vLead * this.vel_scale; }
    this.v_ego += EGO_EMA * ((Number.isFinite(vGps) ? vGps : pose[0]) - this.v_ego);
    this.v_model += EGO_EMA * (pose[0] - this.v_model);
    let dist = xf === null ? null : xf[0];
    if (mot && dist !== null) dist += mot.weight * (mot.dist - dist);
    let gap = null, ttc = null, gapPred = null;
    if (dist !== null) {
      gap = dist - this.d_cam_bumper;
      const closing = this.v_ego - this.v_lead;
      if (closing > 0.5 && gap / closing < TTC_MAX_S) ttc = gap / closing;
      if (mot) gapPred = Math.max(0, mot.predict(PREDICT_S) - this.d_cam_bumper);
    }
    const status = this.coverage < MIN_COVERAGE ? `unreliable: coverage ${pyFixed(this.coverage * 100, 0)}%`
      : this.settled ? "calibrated" : `calibrating ${this.cal.n}/${AutoCalib.SETTLED_SAMPLES}`;
    const tracked = dist !== null;
    return {
      status, rpy: [...this.rpy], height_m: median(this.heights), ego_speed_mps: this.v_ego, lead_prob: prob, gap_m: gap,
      lead_speed_mps: tracked ? this.v_lead : null, ttc_s: ttc, outputs: p, gap_std_m: tracked ? this.gap_std : null,
      lead_lat_m: tracked ? this.lat : null, rpy_est: [...this.cal.est], lead_x_m: dist, lead_raw_m: has ? lx : null,
      gps_speed_mps: Number.isFinite(vGps) ? vGps : null, fy_px: this.K[0][0], gap_pred_m: gapPred, model_speed_mps: this.v_model,
    };
  }
}
