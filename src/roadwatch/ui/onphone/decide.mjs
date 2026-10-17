/* BT-B bản demo (decide.py) cho chạy trên điện thoại: có cần nhắc không, mức nào, vì sao. Hàm thuần: thời gian là giờ
   của khung. Kế hoạch: docs/warning_to_do.md (chỉ theo khoảng cách, không dùng TTC). Phải ra đúng như Python từng khung,
   kể cả câu lý do: tests/roadwatch/js/decide.test.mjs so với dữ liệu chuẩn xuất từ decide.Decider. Tham số là giá trị
   thử nghiệm (đổi thì sửa cả hai nơi). */
import { pyFixed } from "./track.mjs";

export const LEGAL = [[60, 60, 35], [60, 80, 55], [80, 100, 70], [100, 120, 100]];
export const V_STOP_KMH = 5.0, V_CRAWL_KMH = 20.0;
export const NOTICE_S = 3.0, WARN_S = 2.0, SHORT_FRAC = 0.5;
export const BUFFER_FRAC = 0.15, LATENCY_S = 0.3, MAX_RANGE_M = 100.0;
export const T_LEAD_OK = 0.5, T_CONFIRM = 0.5, T_CONFIRM_E = 0.2;
export const REPEAT_FIRST = 3.0, REPEAT_NEXT = 10.0;
export const IMPROVE_MPS = 0.5, CLOSE_FAST_MPS = -5.0, T_CLOSE_FAST = 0.5;
export const T_CLEAR = 3.0, CLEAR_HYST_M = 3.0, T_LOST = 3.0;
export const SLOPE_TAU_S = 0.5, MAX_AGE_S = 0.5, JUMP_M = 10.0;
export const PHRASES = { chime: "(tiếng chuông)", info: "Xe phía trước đang gần lại",
                         warning: "Chú ý giữ khoảng cách xe phía trước", emergency: "(ba tiếng bíp)" };
export const RANK = { chime: 1, info: 2, warning: 3, emergency: 4 };

export function legalGap(kmh) {
  for (const [lo, hi, d] of LEGAL) if (lo <= kmh && kmh <= hi) return d;
  return kmh > LEGAL[LEGAL.length - 1][1] ? LEGAL[LEGAL.length - 1][2] : null;
}

/** [nhắc sớm, cảnh báo, thiếu nhiều] (m) ở tốc độ này, hoặc null dưới V_CRAWL_KMH; nhắc sớm null khi vượt MAX_RANGE_M. */
export function thresholds(kmh) {
  if (kmh < V_CRAWL_KMH) return null;
  const v = kmh / 3.6, d = legalGap(kmh);
  let early, warn;
  if (d === null) { early = v * NOTICE_S; warn = v * WARN_S; }
  else { early = d * (1 + BUFFER_FRAC) + v * LATENCY_S; warn = d < MAX_RANGE_M ? d : v * WARN_S; }
  return [early <= MAX_RANGE_M ? early : null, warn, warn * SHORT_FRAC];
}

const decision = (level, say, reason, threshold, raw = new Set()) => ({ level, say, reason, threshold_m: threshold, raw });
const f0 = (x) => pyFixed(x, 0);

export class Decider {
  constructor() {
    this.prev_gap = this.prev_t = null; this.slope = 0.0;
    this.seen = this.lost = this.fast = this.clear = null;
    this.since = {};
    this._end();
  }

  _end() { this.episode = false; this.top = 0; this.count = 0; this.last_t = null; }

  step(t, gap, egoMps, calibrated, ok = true) {
    const kmh = egoMps * 3.6, th = thresholds(kmh);
    let warn = th ? th[1] : null;
    if (gap === null || !ok) {
      this.prev_gap = this.seen = this.fast = this.clear = null; this.since = {};
      this.lost = this.lost === null ? t : this.lost;
      if (this.episode && t - this.lost > T_LOST) this._end();
      return decision(null, null, "Không có xe trước đủ tin cậy", warn);
    }
    this.lost = null;
    this._rate(t, gap);
    this.seen = this.seen === null ? t : this.seen;
    if (!calibrated || th === null) {
      this.fast = null; this.since = {};
      return decision(null, null, !calibrated ? "Đang hiệu chuẩn: chưa cảnh báo khoảng cách"
        : kmh < V_STOP_KMH ? `Đứng yên (${f0(kmh)} km/h): không nhắc` : `Bò chậm (${f0(kmh)} km/h): chưa nhắc khoảng cách`, warn);
    }
    const [early, , short] = th, zone = early === null ? MAX_RANGE_M : early;
    warn = th[1];
    this.fast = this.slope <= CLOSE_FAST_MPS && gap < zone ? (this.fast === null ? t : this.fast) : null;
    const raw = new Set();
    if (early !== null && gap < early) raw.add("info");
    if (gap < warn) raw.add("warning");
    if (gap < short || (this.fast !== null && t - this.fast >= T_CLOSE_FAST)) raw.add("emergency");
    const since = {};
    for (const k of raw) since[k] = k in this.since ? this.since[k] : t;
    this.since = since;
    let level = null;
    for (const k of raw) {
      if (t - since[k] >= (k === "emergency" ? T_CONFIRM_E : T_CONFIRM) && (level === null || RANK[k] > RANK[level])) level = k;
    }
    this.clear = gap >= zone + CLEAR_HYST_M ? (this.clear === null ? t : this.clear) : null;
    if (this.clear !== null && t - this.clear >= T_CLEAR) this._end();
    if (t - this.seen < T_LEAD_OK) return decision(null, null, "Đang xác nhận xe dẫn đầu", warn, raw);
    if (level && RANK[level] > this.top) {   // tiếng đầu của đợt, hoặc lên mức: phát ngay
      this.episode = true; this.top = RANK[level]; this.count = 0;
      return this._say(t, level, this._why(level, gap, early, warn, short), warn, raw);
    }
    if (early === null && !this.episode) {
      this.episode = true; this.top = RANK.chime; this.count = 0;
      return this._say(t, "chime", `Xe dẫn đầu ${f0(gap)} m ở ${f0(kmh)} km/h: chuông nhắc phòng ngừa`, warn, raw, "info");
    }
    if (level) {
      if (this.slope > IMPROVE_MPS) return decision(level, null, `${f0(gap)} m: đang giãn ra, không nhắc lặp`, warn, raw);
      if (t - this.last_t >= (this.count === 1 ? REPEAT_FIRST : REPEAT_NEXT))
        return this._say(t, level, "Nhắc lại: " + this._why(level, gap, early, warn, short), warn, raw);
      return decision(level, null, `${f0(gap)} m: đang theo dõi`, warn, raw);
    }
    if (this.episode) return decision(early === null ? "info" : null, null, `${f0(gap)} m: đang theo dõi`, warn, raw);
    return decision(null, null, `An toàn: ${f0(gap)} m ≥ ${f0(early)} m`, warn, raw);
  }

  /* tốc độ đổi khoảng cách (m/s, < 0 là đang gần lại): trung bình hàm mũ theo giờ khung, tính lại sau mẫu cũ hoặc nhảy */
  _rate(t, gap) {
    const dt = this.prev_gap === null ? null : t - this.prev_t;
    if (dt === null || dt > MAX_AGE_S || Math.abs(gap - this.prev_gap) > JUMP_M) { this.slope = 0.0; this.fast = null; }
    else if (dt > 0) this.slope += Math.min(1.0, dt / SLOPE_TAU_S) * ((gap - this.prev_gap) / dt - this.slope);
    this.prev_gap = gap; this.prev_t = t;
  }

  _why(level, gap, early, warn, short) {
    if (level === "emergency")
      return gap < short ? `${f0(gap)} m < ${f0(short)} m: thiếu nhiều` : `Khoảng cách giảm nhanh (${pyFixed(this.slope, 1)} m/s)`;
    if (level === "warning") return `${f0(gap)} m < ${f0(warn)} m: dưới khoảng cách cơ sở`;
    return `${f0(gap)} m < ${f0(early)} m: vào vùng nhắc sớm`;
  }

  _say(t, kind, reason, warn, raw, level = null) {
    this.last_t = t; this.count += 1;
    return decision(level || kind, kind, reason, warn, raw);
  }
}
