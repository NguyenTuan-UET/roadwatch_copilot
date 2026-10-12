/* Cảnh cao tốc ban ngày nhìn từ ghế lái, vẽ bằng canvas: dùng cho hero của /app và nền trang tài khoản.
   Chỉ là hình minh hoạ, không có số đo: xe mình chạy về phía trước (vạch đứt, cây, xe làn bên trôi về phía sau),
   xe phía trước giữ khoảng 30 m, vệt làn chiếu phát sáng tới xe phía trước kèm nhãn khoảng cách.
   window.RoadScene(canvas, { vx, horizon, mirror }) -> { start(), stop() }; vx, horizon: tỉ lệ theo chiều rộng / cao. */
(() => {
  "use strict";
  const GLOW = "53,224,200";                                     // xanh ngọc của vệt làn và nhãn
  const SPEED = 24;                                              // m/s: tốc độ xe mình, chỉ để tạo chuyển động
  // xe làn bên: làn, khoảng cách ban đầu, tốc độ so với xe mình (âm = xe mình vượt dần), màu thân
  const TRAFFIC = [[-3.5, 22, -3, "#2f3a45"], [-3.5, 70, -3, "#b8c0c8"], [3.5, 40, 2, "#1d232a"], [3.5, 95, 2, "#9aa4ae"],
    [-7, 55, -6, "#c9cfd5"], [7, 30, 4, "#3a4652"]];
  const FAR = 160, NEAR = 7;

  // số giả ngẫu nhiên cố định: cây và nhà cao tầng đứng yên giữa các lần vẽ
  const rand = (i) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };

  window.RoadScene = function (cv, opt = {}) {
    const g = cv.getContext("2d");
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cars = TRAFFIC.map(([x, d, v, c]) => ({ x, d, v, c }));
    let raf = 0, t0 = 0, last = 0;

    function car(P, x, d, body, label) {
      const [cx, cy] = P(x, d), s = P.scale(d), w = 1.85 * s, h = 1.5 * s;
      g.fillStyle = "rgba(0,0,0,.28)"; g.beginPath(); g.ellipse(cx, cy, w * .6, h * .07, 0, 0, 7); g.fill();
      g.fillStyle = "#15191e"; g.fillRect(cx - w * .46, cy - h * .1, w * .16, h * .1); g.fillRect(cx + w * .3, cy - h * .1, w * .16, h * .1);   // bánh xe
      const lower = g.createLinearGradient(0, cy - h * .6, 0, cy); lower.addColorStop(0, body); lower.addColorStop(1, shade(body, -.25));
      g.fillStyle = lower; g.beginPath(); g.roundRect(cx - w / 2, cy - h * .62, w, h * .55, s * .12); g.fill();
      g.fillStyle = shade(body, -.1); g.beginPath();                                          // mui và kính sau
      g.moveTo(cx - w * .42, cy - h * .6); g.lineTo(cx - w * .32, cy - h); g.lineTo(cx + w * .32, cy - h); g.lineTo(cx + w * .42, cy - h * .6); g.closePath(); g.fill();
      const glass = g.createLinearGradient(0, cy - h * .95, 0, cy - h * .62); glass.addColorStop(0, "#3b4a58"); glass.addColorStop(1, "#11181f");
      g.fillStyle = glass; g.beginPath();
      g.moveTo(cx - w * .36, cy - h * .64); g.lineTo(cx - w * .28, cy - h * .94); g.lineTo(cx + w * .28, cy - h * .94); g.lineTo(cx + w * .36, cy - h * .64); g.closePath(); g.fill();
      g.fillStyle = "#e0343a"; g.fillRect(cx - w * .47, cy - h * .5, w * .2, h * .09); g.fillRect(cx + w * .27, cy - h * .5, w * .2, h * .09);   // đèn hậu
      g.fillStyle = "#e8ecef"; g.fillRect(cx - w * .13, cy - h * .36, w * .26, h * .1);                                                   // biển số
      g.fillStyle = "rgba(0,0,0,.35)"; g.fillRect(cx - w / 2, cy - h * .16, w, h * .07);                                                  // cản sau
      if (!label) return;
      const pad = s * .3, bx = cx - w / 2 - pad, by = cy - h - pad, bw = w + 2 * pad, bh = h + 1.4 * pad;
      g.save(); g.shadowColor = `rgba(${GLOW},.9)`; g.shadowBlur = 12; g.strokeStyle = `rgba(${GLOW},1)`; g.lineWidth = 2; g.strokeRect(bx, by, bw, bh); g.restore();
      g.font = `700 ${Math.max(12, Math.min(24, s * .55))}px system-ui, "Segoe UI", sans-serif`;
      const tw = g.measureText(label).width + 18, th = Math.max(20, Math.min(34, s * .8));
      g.fillStyle = `rgba(${GLOW},.95)`; g.beginPath(); g.roundRect(cx - tw / 2, by - th - 6, tw, th, 5); g.fill();
      g.fillStyle = "#04221e"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(label, cx, by - th / 2 - 6); g.textAlign = "left";
    }
    function shade(hex, k) {   // làm sáng (k > 0) hoặc tối (k < 0) một màu #rrggbb
      const n = parseInt(hex.slice(1), 16), f = (c) => Math.round(k < 0 ? c * (1 + k) : c + (255 - c) * k);
      return `rgb(${f(n >> 16)},${f((n >> 8) & 255)},${f(n & 255)})`;
    }

    function frame(now) {
      const dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
      if (!W || !H) { raf = requestAnimationFrame(frame); return; }
      if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      const t = still ? 8 : Math.max(0, (now - t0) / 1000), dt = still ? 0 : Math.min(0.05, Math.max(0, (now - last) / 1000)); last = now;
      const vx = W * (typeof opt.vx === "function" ? opt.vx(W) : opt.vx ?? 0.6), hy = H * (opt.horizon ?? 0.46), K = (H - hy) * 4;
      const P = (x, d) => [vx + x * K / d / 3.2, hy + K / d]; P.scale = (d) => K / d / 3.2;   // x: mét lệch tâm làn, d: mét phía trước

      // trời, mây, nhà cao tầng ở chân trời
      const sky = g.createLinearGradient(0, 0, 0, hy); sky.addColorStop(0, "#7fb4dc"); sky.addColorStop(1, "#e3eff6");
      g.fillStyle = sky; g.fillRect(0, 0, W, hy + 1);
      for (let i = 0; i < 6; i++) {
        const cx = ((rand(i) * 1.4 + t * 0.004 * (1 + rand(i + 9))) % 1.4 - 0.2) * W, cy = hy * (0.15 + 0.5 * rand(i + 3)), r = W * (0.06 + 0.06 * rand(i + 5));
        const c = g.createRadialGradient(cx, cy, 0, cx, cy, r); c.addColorStop(0, "rgba(255,255,255,.75)"); c.addColorStop(1, "rgba(255,255,255,0)");
        g.fillStyle = c; g.beginPath(); g.ellipse(cx, cy, r, r * .35, 0, 0, 7); g.fill();
      }
      for (let i = 0; i < 26; i++) {
        const bx = vx + (rand(i + 40) - 0.5) * W * 0.5, bw = 8 + 22 * rand(i + 60), bh = hy * (0.04 + 0.16 * rand(i + 80));
        g.fillStyle = `rgba(${110 + 30 * rand(i)},${128 + 30 * rand(i)},${150 + 20 * rand(i)},.75)`; g.fillRect(bx, hy - bh, bw, bh);
      }
      // cỏ hai bên, cây chạy lùi về phía sau
      const grass = g.createLinearGradient(0, hy, 0, H); grass.addColorStop(0, "#7d9a6c"); grass.addColorStop(1, "#4f6b45");
      g.fillStyle = grass; g.fillRect(0, hy, W, H - hy);
      const span = 240, step = 12, off = (t * SPEED) % step;
      for (const side of [-1, 1]) for (let k = 0; k * step < span; k++) {
        const d = 16 + ((k * step - off) % span + span) % span, x = side * (12 + 5 * rand(k + (side > 0 ? 100 : 0)));
        const [tx, ty] = P(x, d), s = P.scale(d), r = s * (1.8 + 0.8 * rand(k + 7));
        if (ty > H + r) continue;
        g.fillStyle = "#4b3a2a"; g.fillRect(tx - s * .15, ty - s * 2.2, s * .3, s * 2.2);
        g.fillStyle = `rgb(${50 + 25 * rand(k)},${95 + 30 * rand(k + 1)},${55 + 20 * rand(k + 2)})`;
        g.beginPath(); g.ellipse(tx, ty - s * 3.4, r, r * 1.15, 0, 0, 7); g.fill();
      }
      // mặt đường: 4 làn rộng 3,5 m, lan can hai bên
      const edge = 7.4, road = [P(-edge, 4), P(edge, 4), P(edge, 600), P(-edge, 600)];
      const asphalt = g.createLinearGradient(0, hy, 0, H); asphalt.addColorStop(0, "#8b939b"); asphalt.addColorStop(1, "#555d66");
      g.fillStyle = asphalt; g.beginPath(); road.forEach(([x, y], i) => i ? g.lineTo(x, y) : g.moveTo(x, y)); g.closePath(); g.fill();
      for (const x of [-edge - .4, edge + .4]) {
        g.strokeStyle = "#c8ced3"; g.lineWidth = 2; g.beginPath();
        for (let d = 4; d < 400; d *= 1.15) { const [px, py] = P(x, d), up = P.scale(d) * .8; d === 4 ? g.moveTo(px, py - up) : g.lineTo(px, py - up); }
        g.stroke();
      }
      g.strokeStyle = "rgba(245,247,249,.9)"; g.lineWidth = 2;
      for (const x of [-7, 7]) { g.beginPath(); g.moveTo(...P(x, 4)); g.lineTo(...P(x, 600)); g.stroke(); }
      const dash = (t * SPEED) % 12;
      g.fillStyle = "rgba(245,247,249,.9)";
      for (const x of [-3.5, 3.5]) for (let d = 4 - dash; d < 300; d += 12) {
        const d1 = Math.max(4, d), d2 = d + 6; if (d2 <= 4) continue;
        g.beginPath(); g.moveTo(...P(x - .08, d1)); g.lineTo(...P(x + .08, d1)); g.lineTo(...P(x + .08, d2)); g.lineTo(...P(x - .08, d2)); g.fill();
      }

      // xe phía trước: cùng tốc độ, khoảng cách dao động nhẹ quanh 32 m
      const lead = 32 + 4 * Math.sin(t * 0.5);
      // vệt làn chiếu: hai mép làn mình phát sáng từ đầu xe mình tới xe phía trước
      const lane = [P(-1.75, 4), P(1.75, 4), P(1.75, lead), P(-1.75, lead)];
      const fill = g.createLinearGradient(0, lane[0][1], 0, lane[2][1]); fill.addColorStop(0, `rgba(${GLOW},.28)`); fill.addColorStop(1, `rgba(${GLOW},.06)`);
      g.fillStyle = fill; g.beginPath(); lane.forEach(([x, y], i) => i ? g.lineTo(x, y) : g.moveTo(x, y)); g.closePath(); g.fill();
      g.save(); g.shadowColor = `rgba(${GLOW},1)`; g.shadowBlur = 20; g.strokeStyle = `rgba(${GLOW},1)`; g.lineWidth = 4;
      for (const x of [-1.75, 1.75]) { g.beginPath(); g.moveTo(...P(x, 4)); g.lineTo(...P(x, lead)); g.stroke(); }
      g.restore();
      g.strokeStyle = `rgba(${GLOW},.25)`; g.lineWidth = 1;
      for (let k = 6; k < lead; k += 3) { g.beginPath(); g.moveTo(...P(-1.75, k)); g.lineTo(...P(1.75, k)); g.stroke(); }

      // xe làn bên: xe chậm hơn trôi về phía sau rồi xuất hiện lại ở xa, xe nhanh hơn chạy vượt lên rồi quay lại
      for (const c of cars) { c.d += c.v * dt; if (c.d < NEAR) c.d = FAR; if (c.d > FAR) c.d = NEAR + 4; }
      const all = cars.map((c) => [c.x, c.d, c.c, null]).concat([[0, lead, "#e9edf1", `${Math.round(lead)} m`]]);
      all.sort((a, b) => b[1] - a[1]);
      for (const [x, d, c, label] of all) car(P, x, d, c, label);

      // khung kính lái, gương chiếu hậu, táp-lô với vô lăng và đồng hồ 80 km/h
      const top = g.createLinearGradient(0, 0, 0, H * .07); top.addColorStop(0, "#0b0e12"); top.addColorStop(1, "rgba(11,14,18,0)");
      g.fillStyle = top; g.fillRect(0, 0, W, H * .07);
      if (opt.mirror) { g.fillStyle = "#14181d"; g.beginPath(); g.roundRect(vx - W * .09, H * .02, W * .18, H * .09, H * .03); g.fill(); g.fillRect(vx - 3, 0, 6, H * .03); }
      const dashY = H * .84;
      g.fillStyle = "#101418"; g.beginPath(); g.moveTo(0, dashY + H * .03); g.quadraticCurveTo(W / 2, dashY - H * .04, W, dashY + H * .03); g.lineTo(W, H); g.lineTo(0, H); g.closePath(); g.fill();
      const wx = vx - W * .02, wr = Math.min(W * .2, H * .32);
      g.strokeStyle = "#1c2228"; g.lineWidth = wr * .14; g.beginPath(); g.ellipse(wx, H + wr * .25, wr, wr * .62, 0, Math.PI, 2 * Math.PI); g.stroke();
      g.fillStyle = "#0a0d10"; g.beginPath(); g.ellipse(wx, H * .99, wr * .55, H * .07, 0, Math.PI, 2 * Math.PI); g.fill();
      g.fillStyle = "#e9eef2"; g.textAlign = "center"; g.textBaseline = "alphabetic";
      g.font = `600 ${Math.max(14, H * .045)}px system-ui, "Segoe UI", sans-serif`; g.fillText("80", wx, H * .985);
      g.textAlign = "left";
      if (!still) raf = requestAnimationFrame(frame);
    }
    return {
      start() { if (!raf) { t0 = last = performance.now(); raf = requestAnimationFrame(frame); } },
      stop() { cancelAnimationFrame(raf); raf = 0; },
    };
  };
})();
