/* BT-B bản demo (decide.py) cho chạy trên điện thoại: có cần nhắc không, mức nào, vì sao. Hàm thuần: thời gian là giờ
   của khung. Phải ra đúng như Python từng khung, kể cả câu lý do: tests/roadwatch/js/decide.test.mjs so với dữ liệu
   chuẩn xuất từ decide.Decider. Tham số là giá trị tạm của cấu hình đề xuất (đổi thì sửa cả hai nơi). */
import { pyFixed } from "./track.mjs";

export const LEGAL = [[60, 60, 35], [60, 80, 55], [80, 100, 70], [100, 120, 100]];
export const TTC_EMERGENCY_S = 1.8, H_TTC_S = 0.5, T_CLEAR_E_S = 1.5;
export const T_CONFIRM_S = 1.5, H_M = 5.0, T_CLEAR_S = 2.0, COOLDOWN_S = 10.0;
export const INFO_HORIZON_S = 3.0, GRACE_S = 4.0, CUT_IN_DROP_M = 10.0;
export const PHRASES = { emergency: "Sắp xảy ra va chạm", warning: "Chú ý giữ khoảng cách xe phía trước", info: "Xe phía trước đang gần lại" };
export const RANK = { emergency: 3, warning: 2, info: 1 };
const pyNum = (x) => (Number.isInteger(x) ? x.toFixed(1) : String(x));   // f"{1.5}" -> "1.5", f"{2.0}" -> "2.0"

export function legalGap(kmh) {
  for (const [lo, hi, d] of LEGAL) if (lo <= kmh && kmh <= hi) return d;
  return kmh > LEGAL[LEGAL.length - 1][1] ? LEGAL[LEGAL.length - 1][2] : null;
}

const decision = (level, say, reason, threshold, raw) => ({ level, say, reason, threshold_m: threshold, raw });

export class Decider {
  constructor() {
    this.prev_gap = this.prev_t = null; this.grace_until = -1.0;
    this.below_since = this.above_since = this.e_clear_since = null;
    this.warn_active = this.e_active = false;
    this.last_said = {}; this.slope = 0.0;
  }

  step(t, gap, egoMps, ttc, calibrated, ttcOk = true) {
    const kmh = egoMps * 3.6, d = legalGap(kmh), raw = new Set();
    if (ttcOk && ttc !== null && ttc <= TTC_EMERGENCY_S) {
      raw.add("emergency");
      this.e_clear_since = null;
      if (!this.e_active) {
        this.e_active = true;
        return this._say(t, "emergency", `TTC ${pyFixed(ttc, 1)} s ≤ ${pyNum(TTC_EMERGENCY_S)} s: phát ngay`, d, raw);
      }
    } else if (this.e_active) {
      if (ttc === null || ttc > TTC_EMERGENCY_S + H_TTC_S) {
        this.e_clear_since = this.e_clear_since === null ? t : this.e_clear_since;
        if (t - this.e_clear_since >= T_CLEAR_E_S) this.e_active = false;
      }
    }
    if (this.e_active) return decision("emergency", null, "Khẩn cấp: đã phát trong đợt này", d, raw);

    if (gap === null) {
      this.prev_gap = null; this.prev_t = null; this.below_since = null;
      return decision(null, null, "Không có xe trước đủ tin cậy", d, raw);
    }
    if (this.prev_gap === null || this.prev_gap - gap > CUT_IN_DROP_M) { this.grace_until = t + GRACE_S; this.slope = 0.0; }
    else if (t > this.prev_t) this.slope = 0.9 * this.slope + 0.1 * (gap - this.prev_gap) / (t - this.prev_t);   // m/s, theo giờ khung
    this.prev_gap = gap; this.prev_t = t;
    if (!calibrated) return decision(null, null, "Đang hiệu chuẩn: chưa cảnh báo khoảng cách", d, raw);
    if (d === null) {
      this.below_since = null;
      return decision(null, null, `Ùn tắc (${pyFixed(kmh, 0)} km/h < 60): tắt nhắc khoảng cách, vẫn giữ cảnh báo va chạm`, d, raw);
    }
    const margin = d + (this.warn_active ? H_M : 0.0);
    if (gap < margin) {
      raw.add("warning");
      this.above_since = null;
      this.below_since = this.below_since === null ? t : this.below_since;
    } else {
      this.below_since = null;
      if (this.warn_active) {
        this.above_since = this.above_since === null ? t : this.above_since;
        if (t - this.above_since >= T_CLEAR_S) this.warn_active = false;
      }
    }
    const forecast = gap + this.slope * INFO_HORIZON_S;
    if (gap >= d && forecast < d) raw.add("info");
    if (t < this.grace_until && [...raw].some((k) => k !== "emergency"))
      return decision(null, null, `Ân hạn xe mới chen vào: còn ${pyFixed(this.grace_until - t, 1)} s`, d, raw);
    if (raw.has("warning") && t - this.below_since >= T_CONFIRM_S) {
      this.warn_active = true;
      if (this._ready(t, "warning"))
        return this._say(t, "warning", `${pyFixed(gap, 0)} m < ngưỡng ${pyFixed(d, 0)} m quá ${pyNum(T_CONFIRM_S)} s`, d, raw);
      return decision("warning", null, `Dưới ngưỡng ${pyFixed(d, 0)} m, đang trong thời gian chờ nhắc lại`, d, raw);
    }
    if (raw.has("warning")) return decision(null, null, `Dưới ngưỡng, chờ xác nhận ${pyNum(T_CONFIRM_S)} s`, d, raw);
    if (raw.has("info")) {
      if (this._ready(t, "info"))
        return this._say(t, "info", `${pyFixed(gap, 0)} m, dự báo ${pyFixed(forecast, 0)} m sau ${pyFixed(INFO_HORIZON_S, 0)} s`, d, raw);
      return decision("info", null, "Đang thu hẹp, trong thời gian chờ nhắc lại", d, raw);
    }
    return decision(null, null, `An toàn: ${pyFixed(gap, 0)} m ≥ ngưỡng ${pyFixed(d, 0)} m`, d, raw);
  }

  _ready(t, kind) { return t - (kind in this.last_said ? this.last_said[kind] : -1e9) >= COOLDOWN_S; }
  _say(t, kind, reason, d, raw) { this.last_said[kind] = t; return decision(kind, kind, reason, d, raw); }
}
