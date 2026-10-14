/* Các hàm numpy mà phần làn (lanes.mjs, geometry.mjs) cần, cùng cách tính: np.interp, np.linspace, np.arange,
   np.polyfit (bình phương tối thiểu, hệ số bậc cao trước), np.polyval, np.polyder, np.median. Số thực 64 bit. */

/** np.interp với x là một số: giữ giá trị biên ngoài khoảng xp (tăng dần). */
export function interp(x, xp, fp) {
  if (x <= xp[0]) return fp[0];
  if (x >= xp[xp.length - 1]) return fp[fp.length - 1];
  let i = 1; while (xp[i] < x) i++;
  return fp[i - 1] + (fp[i] - fp[i - 1]) * (x - xp[i - 1]) / (xp[i] - xp[i - 1]);
}

export const linspace = (a, b, n) => Array.from({ length: n }, (_, i) => (i === n - 1 ? b : a + (b - a) * i / (n - 1)));

export function arange(a, b, step) {
  const n = Math.max(0, Math.ceil((b - a) / step));
  return Array.from({ length: n }, (_, i) => a + i * step);
}

/** Hệ số (bậc cao trước) của đa thức bậc deg khớp (xs, ys) theo bình phương tối thiểu. Giải bằng QR (Householder)
    trên x đã đưa về [-1, 1] rồi đổi lại hệ số: không mất chính xác khi x tới 80 và bậc 3. */
export function polyfit(xs, ys, deg) {
  const m = xs.length, n = deg + 1, x0 = (Math.max(...xs) + Math.min(...xs)) / 2, s = (Math.max(...xs) - Math.min(...xs)) / 2 || 1;
  const A = xs.map((x) => { const t = (x - x0) / s; return Array.from({ length: n }, (_, j) => t ** (deg - j)); });
  const b = [...ys];
  for (let k = 0; k < n; k++) {   // Householder: A = QR, b <- Q^T b
    let norm = 0; for (let i = k; i < m; i++) norm += A[i][k] ** 2;
    norm = Math.sqrt(norm);
    if (!norm) continue;
    const alpha = A[k][k] > 0 ? -norm : norm, v = new Array(m).fill(0);
    v[k] = A[k][k] - alpha; for (let i = k + 1; i < m; i++) v[i] = A[i][k];
    const vv = v.reduce((a, x) => a + x * x, 0);
    if (!vv) continue;
    for (let j = k; j < n; j++) {
      let d = 0; for (let i = k; i < m; i++) d += v[i] * A[i][j];
      for (let i = k; i < m; i++) A[i][j] -= 2 * d / vv * v[i];
    }
    let d = 0; for (let i = k; i < m; i++) d += v[i] * b[i];
    for (let i = k; i < m; i++) b[i] -= 2 * d / vv * v[i];
  }
  const ct = new Array(n).fill(0);   // hệ số theo t, bậc cao trước
  for (let k = n - 1; k >= 0; k--) {
    let r = b[k]; for (let j = k + 1; j < n; j++) r -= A[k][j] * ct[j];
    ct[k] = r / A[k][k];
  }
  // p(x) = sum ct[j] ((x - x0) / s)^(deg - j): khai triển nhị thức về lũy thừa của x
  const out = new Array(n).fill(0), binom = (a, k) => { let r = 1; for (let i = 1; i <= k; i++) r = r * (a - k + i) / i; return r; };
  for (let j = 0; j < n; j++) {
    const p = deg - j;
    for (let k = 0; k <= p; k++) out[deg - k] += ct[j] * binom(p, k) * (-x0) ** (p - k) / s ** p;
  }
  return out;
}

export const polyval = (c, x) => c.reduce((acc, v) => acc * x + v, 0);
export const polyder = (c) => c.slice(0, -1).map((v, i) => v * (c.length - 1 - i));

/** np.median: của một mảng số, hoặc từng phần tử qua nhiều mảng cùng độ dài (axis=0). */
export function median(xs) {
  if (!Array.isArray(xs[0])) {
    const s = [...xs].sort((a, b) => a - b), k = s.length >> 1;
    return s.length % 2 ? s[k] : (s[k - 1] + s[k]) / 2;
  }
  return xs[0].map((_, i) => median(xs.map((a) => a[i])));
}
