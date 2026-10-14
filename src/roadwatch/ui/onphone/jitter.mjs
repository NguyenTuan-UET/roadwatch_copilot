/* Độ rung của một đại lượng theo thời gian (vị trí mép thảm làn ở 15 m): căn bậc hai trung bình bình phương của gia
   tốc (sai phân bậc hai chia dt²) tính bằng đơn vị/s², nên so được giữa các tốc độ khung khác nhau; và p95 tốc độ đổi.
   Dùng ở engine.mjs để ghi nhật ký từng khung thay vì mẫu 5 s (14/10/2026: đánh giá làn trên iPhone bằng mắt). */
export class Jitter {
  constructor() { this.reset(); }
  reset() { this.t = []; this.v = []; }
  add(t, v) { this.t.push(t); this.v.push(v); if (this.t.length > 600) { this.t.shift(); this.v.shift(); } }
  summary() {
    const { t, v } = this, n = t.length;
    if (n < 3) return { n, accel_rms: null, rate_p95: null };
    let s = 0; const rates = [];
    for (let i = 2; i < n; i++) {
      const a = ((v[i] - v[i - 1]) / (t[i] - t[i - 1]) - (v[i - 1] - v[i - 2]) / (t[i - 1] - t[i - 2])) / ((t[i] - t[i - 2]) / 2);
      s += a * a;
    }
    for (let i = 1; i < n; i++) rates.push(Math.abs(v[i] - v[i - 1]) / (t[i] - t[i - 1]));
    rates.sort((a, b) => a - b);
    return { n, accel_rms: Math.sqrt(s / (n - 2)), rate_p95: rates[Math.min(rates.length - 1, Math.floor(0.95 * rates.length))] };
  }
}
