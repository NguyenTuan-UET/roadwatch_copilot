/* Màn buồng lái mở đầu, góc nhìn từ ghế lái. Nội thất là ảnh buồng lái low-poly (cockpit.jpg); kính chắn gió được khoét trống
   và phía sau là cảnh 3D dựng bằng canvas 2D (chiếu phối cảnh, vẽ từ xa tới gần, không thư viện, không CDN, chạy offline):
   đường ba làn, cây, hàng rào, cột đèn, cổng biển báo, camera phạt nguội, người đi bộ, xe phía trước và xe cùng đường, tất cả
   chạy về phía tài xế đúng 68 km/h. Vô lăng tách khỏi ảnh để xoay được. Chạm chữ V: phóng to vào màn hình trung tâm, logo hiện
   lên, rồi vào web app ở /app. */
(function () {
  "use strict";
  // Chạm V xong thì vào web app (không nhúng iframe: server gửi X-Frame-Options DENY).
  const ENTER_URL = "/app#intro";
  const PHOTO = "/ui/cockpit.jpg";                 // ảnh buồng lái 1673×940; cùng nguồn nên đọc được điểm ảnh
  const W = 1673, H = 940;
  const $ = (id) => document.getElementById(id);
  const REDUCED = false;                             // bản demo: luôn chạy hoạt cảnh, kể cả khi máy bật "giảm chuyển động"
  const cv = $("cv"), ctx = cv.getContext("2d"), cvs = $("cvs"), sctx = cvs.getContext("2d");

  // toạ độ đo trên ảnh
  const RIM = { cx: 367, cy: 546, rx: 250, ry: 216 };            // mép ngoài vành vô lăng
  const OPENING = [[180, 520], [186, 470], [206, 435], [240, 410], [290, 395], [367, 389], [445, 395], [495, 410], [530, 435], [550, 470], [556, 520], [470, 515], [440, 500], [295, 500], [265, 515]]; // cụm đồng hồ nhìn qua vô lăng
  const LOGO = { cx: 355, cy: 574 };
  const SCREEN = { cx: 834, cy: 480, w: 416, h: 220, view: [648, 418, 300, 152] };   // màn hình trung tâm; view: ô cảnh phía trước
  // kính chắn gió: trụ trái, mép trên, trụ phải, mép bảng điều khiển (vành vô lăng nhô lên phía trên mép này nên đi vòng qua)
  const WINDSHIELD = [[82, 0], [1615, 0], [1595, 50], [1572, 100], [1550, 150], [1525, 200], [1500, 250], [1475, 300], [1447, 350], [1435, 378], [1400, 371], [1200, 362], [1000, 355], [850, 352], [560, 350], [505, 343], [475, 333], [440, 329], [300, 331], [262, 342], [240, 356], [232, 362], [225, 350], [195, 300], [175, 250], [157, 200], [140, 150], [125, 100], [110, 50]];
  const MIRROR = [640, 0, 385, 112];                 // ô chứa gương chiếu hậu: giữ lại những điểm tối hơn bầu trời
  const CRUISE = 68 / 3.6, LOOP = 260, OUT = "#0f171e";
  // gap: khoảng cách tới đuôi xe phía trước (m); hai khung chọn để xe đứng đúng chỗ như trong ảnh mẫu
  const WS = { hx: 800, hy: 240, f: 1250, camH: 1.25, w: W, h: 382, lw: 2.2, k: 1, gap: 24 };        // kính chắn gió
  const SV = { hx: 176, hy: 24, f: 520, camH: 1.73, w: 300, h: 152, lw: 0.9, k: 0.4, lod: true, gap: 18 };   // cảnh trong màn hình trung tâm (toạ độ cục bộ)

  // ---------- dữ liệu cảnh ----------
  const rngOf = (seed) => () => { seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const GREENS = [[104, 184, 84], [124, 202, 98], [88, 166, 76], [142, 208, 108]], SKYC = [214, 232, 244];
  const items = (() => {
    const rnd = rngOf(20261014), list = [];
    for (const s of [-1, 1]) {
      for (let z = 0; z < LOOP; z += 7) list.push({ k: "tree", x: s * (11 + rnd() * 16), z: z + rnd() * 6, r: 2.2 + rnd() * 1.4, th: 2.8 + rnd() * 1.6, g: GREENS[(rnd() * 4) | 0], j: Array.from({ length: 9 }, () => 0.86 + rnd() * 0.26) });
      for (let z = 0; z < LOOP; z += 11) list.push({ k: "tree", x: s * (9.8 + rnd() * 0.8), z: z + rnd() * 8, r: 0.8 + rnd() * 0.5, th: 0.1, g: GREENS[(rnd() * 4) | 0], j: Array.from({ length: 9 }, () => 0.86 + rnd() * 0.26) });
      for (let z = 0; z < LOOP; z += 52) list.push({ k: "lamp", x: s * 8.9, z: z + (s > 0 ? 0 : 26) });
      for (let z = 0; z < LOOP; z += 6) list.push({ k: "post", x: s * 8.3, z });
    }
    return list;
  })();
  const TRAFFIC = [{ x: -3.5, z: 70, rel: 3.2, c: [150, 160, 172] }, { x: -3.5, z: 160, rel: 2.1, c: [226, 230, 236] }, { x: 3.5, z: 110, rel: 1.4, c: [110, 150, 210] }, { x: 3.5, z: 220, rel: 2.6, c: [236, 238, 240] }, { x: -3.5, z: 230, rel: 4.1, c: [96, 106, 120] }];
  const CLOUDS = [{ x: 0.1, y: 0.35, s: 1, v: 5 }, { x: 0.45, y: 0.2, s: 1.4, v: 3 }, { x: 0.72, y: 0.5, s: 0.8, v: 6 }, { x: 0.9, y: 0.28, s: 1.1, v: 4 }];
  const mod = (a, n) => ((a % n) + n) % n;
  const tintH = (c, k, hz) => `rgb(${[0, 1, 2].map((i) => Math.min(255, Math.round(c[i] * k * (1 - hz) + SKYC[i] * hz))).join(",")})`;
  const tint = (c, k) => `rgb(${Math.min(255, Math.round(c[0] * k))},${Math.min(255, Math.round(c[1] * k))},${Math.min(255, Math.round(c[2] * k))})`;

  function bracket(g, x0, y0, x1, y1, lw, len) {
    g.beginPath();
    g.moveTo(x0, y0 + len); g.lineTo(x0, y0); g.lineTo(x0 + len, y0); g.moveTo(x1 - len, y0); g.lineTo(x1, y0); g.lineTo(x1, y0 + len);
    g.moveTo(x1, y1 - len); g.lineTo(x1, y1); g.lineTo(x1 - len, y1); g.moveTo(x0 + len, y1); g.lineTo(x0, y1); g.lineTo(x0, y1 - len);
    g.lineWidth = lw; g.stroke();
  }
  function chip(g, x, y, text, bg, fg, fs, icon, border) {
    g.save(); g.font = `700 ${fs}px system-ui, "Segoe UI", sans-serif`; const tw = g.measureText(text).width, pw = fs * 0.55, w = tw + pw * 2 + (icon ? fs * 1.2 : 0), h = fs * 1.75;
    g.fillStyle = bg; g.shadowColor = bg; g.shadowBlur = fs * 0.9; g.beginPath(); g.roundRect(x, y, w, h, fs * 0.3); g.fill(); g.shadowBlur = 0; if (border) { g.strokeStyle = border; g.lineWidth = 1.5; g.stroke(); }
    g.fillStyle = fg; g.textAlign = "left"; g.textBaseline = "middle"; g.fillText(text, x + pw + (icon ? fs * 1.2 : 0), y + h / 2 + 1);
    if (icon) { g.strokeStyle = fg; g.lineWidth = fs * 0.12; g.strokeRect(x + pw, y + h * 0.28, fs * 0.9, h * 0.44); g.beginPath(); g.arc(x + pw + fs * 0.45, y + h / 2, fs * 0.16, 0, 6.3); g.stroke(); }
    g.restore();
  }

  // ---------- cảnh 3D phía ngoài ----------
  // Hệ toạ độ thế giới (m): x sang phải, y lên, z về phía trước tính từ mắt tài xế; st = { d: quãng đường, t, pan, sway }
  function renderWorld(g, V, st, hud) {
    const { f, camH, lw, w, h } = V, hx = V.hx + st.pan, hy = V.hy, cx = st.sway, d = st.d;
    const P = (X, Y, Z) => [hx + (f * (X - cx)) / Z, hy - (f * (Y - camH)) / Z];
    const quad = (pts, fill, stroke, sw) => {
      g.beginPath();
      for (let i = 0; i < pts.length; i++) { const p = pts[i]; if (p[2] < 0.8) return; const q = P(p[0], p[1], p[2]); if (i) g.lineTo(q[0], q[1]); else g.moveTo(q[0], q[1]); }
      g.closePath(); if (fill) { g.fillStyle = fill; g.fill(); } if (stroke) { g.strokeStyle = stroke; g.lineWidth = sw || lw; g.lineJoin = "round"; g.stroke(); }
    };
    const NEAR = 1.2, FAR = 420;
    // trời nhạt, mặt đất sáng (kiểu mô hình ADAS 3D)
    const sk = g.createLinearGradient(0, 0, 0, hy); sk.addColorStop(0, "#74b4e8"); sk.addColorStop(1, "#dcecf6"); g.fillStyle = sk; g.fillRect(0, 0, w, hy + 1);
    const gr = g.createLinearGradient(0, hy, 0, h); gr.addColorStop(0, "#b5e08e"); gr.addColorStop(1, "#7fc45e"); g.fillStyle = gr; g.fillRect(0, hy, w, h - hy);
    // mặt đường: nền, dải sáng tối chạy theo quãng đường, vạch biên, lề đường, vỉa hè, vạch làn
    quad([[-7, 0, NEAR], [7, 0, NEAR], [7, 0, FAR], [-7, 0, FAR]], "#464a52");
    const BS = 10, b0 = Math.floor(d / BS);
    for (let k = 0; k < FAR / BS + 1; k++) {
      if ((b0 + k) % 2) continue; const z0 = Math.max(NEAR, k * BS - (d % BS)), z1 = (k + 1) * BS - (d % BS); if (z1 <= NEAR) continue;
      quad([[-7, 0, z0], [7, 0, z0], [7, 0, z1], [-7, 0, z1]], "#4e525b");
    }
    for (const x of [-6.7, 6.7]) quad([[x - 0.1, 0, NEAR], [x + 0.1, 0, NEAR], [x + 0.1, 0, FAR], [x - 0.1, 0, FAR]], "#f4f4ef");
    quad([[-7.6, 0, NEAR], [-7, 0, NEAR], [-7, 0, FAR], [-7.6, 0, FAR]], "#cfcabd");
    quad([[7.6, 0, NEAR], [11, 0, NEAR], [11, 0, FAR], [7.6, 0, FAR]], "#d8d2c4");
    for (let k = 0; k < FAR / 4; k++) {
      const z0 = Math.max(NEAR, k * 4 - (d % 4)), z1 = (k + 1) * 4 - (d % 4); if (z1 <= NEAR) continue;
      quad([[7, 0, z0], [7.6, 0, z0], [7.6, 0, z1], [7, 0, z1]], (Math.floor(d / 4) + k) % 2 ? "#f2c230" : "#3a3f47");
    }
    for (const x of [-5.25, -1.75, 1.75, 5.25]) for (let k = 0; k < FAR / 9; k++) {
      const z0 = Math.max(NEAR, k * 9 - (d % 9)), z1 = k * 9 - (d % 9) + 3; if (z1 <= NEAR) continue;
      quad([[x - 0.1, 0, z0], [x + 0.1, 0, z0], [x + 0.1, 0, z1], [x - 0.1, 0, z1]], "#f7f7f2");
    }
    for (const x of [-8.3, 8.3]) { quad([[x, 0.55, NEAR], [x, 0.55, FAR], [x, 0.88, FAR], [x, 0.88, NEAR]], "#d3dae0"); quad([[x, 0.88, NEAR], [x, 0.88, FAR], [x, 0.84, FAR], [x, 0.84, NEAR]], "#8d99a4"); }
    const hz = g.createLinearGradient(0, hy - f * 0.04, 0, hy + f * 0.05); hz.addColorStop(0, "rgba(214,226,232,0)"); hz.addColorStop(0.5, "rgba(214,226,232,.8)"); hz.addColorStop(1, "rgba(214,226,232,0)");
    g.fillStyle = hz; g.fillRect(0, hy - f * 0.04, w, f * 0.09);
    // vật thể theo thứ tự xa tới gần
    const vis = [], fade = (z, end) => Math.max(0, Math.min(1, (end - z) / 70));
    for (const it of items) { if (V.lod && it.k === "post") continue; const z = mod(it.z - d, LOOP); if (z > 7) vis.push({ z, it }); }
    const gz = mod(190 - d, 560); if (gz > 7) vis.push({ z: gz, kind: "gantry" });
    const pz = mod(110 - d, 430); if (pz > 7) vis.push({ z: pz, kind: "pole" });
    for (const c of TRAFFIC) { const z = mod(c.z + c.rel * st.t - 10, 250) + 10; vis.push({ z, kind: "car", c }); }
    const dz = mod(60 - d, 330); if (dz > 7) vis.push({ z: dz, kind: "ped" });
    vis.push({ z: V.gap + 2.2, kind: "lead" });
    vis.sort((a, b) => b.z - a.z);
    for (const v of vis) {
      const z = v.z, it = v.it; g.globalAlpha = fade(z, v.kind === "ped" ? 330 : v.kind === "gantry" ? 560 : v.kind === "pole" ? 430 : v.kind === "car" ? 260 : LOOP);
      if (it && it.k === "tree") {
        const u = f / z, [px, py] = P(it.x, 0, z), R = it.r * u, th = it.th * u, cyc = py - th - R, hzv = Math.min(0.6, Math.max(0, (z - 40) / 300));
        if (px + R < 0 || px - R > w) continue;
        const tw = Math.max(1, 0.5 * u); g.fillStyle = tintH([168, 144, 118], 1, hzv); g.fillRect(px - tw / 2, py - th - R * 0.3, tw, th + R * 0.3);
        if (V.lod || R < 9) { g.fillStyle = tintH(it.g, 1, hzv); g.beginPath(); g.ellipse(px, cyc, R, R * 1.15, 0, 0, 6.3); g.fill(); }
        else {   // tán cây nhiều mặt phẳng (low-poly): vành ngoài, vành trong, đỉnh
          const N = 9, O = [], I = [], c0 = [px + R * 0.05, cyc - R * 0.35];
          for (let i = 0; i < N; i++) { const a = (i / N) * 6.2832, j = it.j[i]; O.push([px + Math.cos(a) * R * j, cyc + Math.sin(a) * R * 1.2 * j]); I.push([px + Math.cos(a + 0.35) * R * 0.52 * j + R * 0.06, cyc + Math.sin(a + 0.35) * R * 0.66 * j - R * 0.2]); }
          const tri = (A, B, C, sh) => { g.fillStyle = tintH(it.g, sh, hzv); g.beginPath(); g.moveTo(A[0], A[1]); g.lineTo(B[0], B[1]); g.lineTo(C[0], C[1]); g.closePath(); g.fill(); g.strokeStyle = g.fillStyle; g.lineWidth = 0.6; g.stroke(); };
          for (let i = 0; i < N; i++) {
            const n = (i + 1) % N, am = ((i + 0.5) / N) * 6.2832, dot = -0.7 * Math.cos(am) - 0.7 * Math.sin(am), jt = (it.j[i] - 1) * 0.5;
            tri(O[i], O[n], I[i], 0.86 + 0.26 * dot + jt); tri(O[n], I[n], I[i], 0.92 + 0.26 * dot - jt); tri(c0, I[i], I[n], 1.04 + 0.2 * dot + jt);
          }
        }
      } else if (it && it.k === "lamp") {
        const [px, py] = P(it.x, 0, z), u = f / z, hh = 10 * u, pw = Math.max(1, 0.3 * u), arm = -Math.sign(it.x) * 2.4 * u;
        g.fillStyle = "#aebac4"; g.fillRect(px - pw / 2, py - hh, pw, hh); g.fillRect(Math.min(px, px + arm), py - hh, Math.abs(arm), Math.max(1, 0.12 * u));
        g.fillStyle = "#fff6c8"; g.fillRect(px + arm - 0.35 * u, py - hh, 0.7 * u, Math.max(1, 0.18 * u));
      } else if (it && it.k === "post") {
        const a = P(it.x, 0, z), u = f / z, pw = Math.max(1, 0.26 * u); g.fillStyle = "#a9aeb4"; g.fillRect(a[0] - pw / 2, a[1] - 0.9 * u, pw, 0.9 * u);
      } else if (v.kind === "car" || v.kind === "lead") {
        const lead = v.kind === "lead", X = lead ? 0 : v.c.x, col = lead ? [150, 160, 172] : v.c.c;
        drawCar(quad, X, z, col, lead, lw);
      } else if (v.kind === "gantry") {
        for (const X of [-9.6, 9.6]) quad([[X - 0.25, 0, z], [X + 0.25, 0, z], [X + 0.25, 7, z], [X - 0.25, 7, z]], "#aab4bd", OUT);
        quad([[-9.8, 6.3, z], [9.8, 6.3, z], [9.8, 7.1, z], [-9.8, 7.1, z]], "#c2cbd3", OUT);
        for (const [a, b] of [[-6.4, -1.4], [1.2, 6.2]]) {
          quad([[a, 3.9, z], [b, 3.9, z], [b, 6.2, z], [a, 6.2, z]], "#2fa05a", "rgba(255,255,255,.7)", lw);
          for (const yy of [5.5, 4.8]) quad([[a + 0.5, yy, z], [b - 0.9, yy, z], [b - 0.9, yy - 0.28, z], [a + 0.5, yy - 0.28, z]], "#fff");
        }
      } else if (v.kind === "ped") {
        const X = 9.2, sw = Math.sin(st.t * 5);
        for (const sg of [-1, 1]) { const o = sg * sw * 0.16; quad([[X + sg * 0.12 + o - 0.08, 0, z], [X + sg * 0.12 + o + 0.08, 0, z], [X + sg * 0.12 + 0.08, 0.86, z], [X + sg * 0.12 - 0.08, 0.86, z]], "#1b2342"); }
        quad([[X - 0.25, 0.82, z], [X + 0.25, 0.82, z], [X + 0.27, 1.5, z], [X - 0.27, 1.5, z]], "#2b4a8c");
        quad([[X - 0.21, 0.95, z - 0.1], [X + 0.21, 0.95, z - 0.1], [X + 0.21, 1.42, z - 0.1], [X - 0.21, 1.42, z - 0.1]], "#181d30");
        { const [hx2, hy2] = P(X, 1.66, z), r = Math.max(1, 0.14 * f / z); g.fillStyle = "#c8946e"; g.beginPath(); g.arc(hx2, hy2, r, 0, 6.3); g.fill(); g.fillStyle = "#1b1b24"; g.beginPath(); g.arc(hx2, hy2, r * 1.02, Math.PI, 6.3); g.fill(); }
        if (hud && z > 9 && z < 110) { const [x0, y0] = P(X - 0.55, 1.95, z), [x1, y1] = P(X + 0.55, 0, z); hud.push(() => { g.save(); g.strokeStyle = "#ff3344"; g.shadowColor = "#ff3344"; g.shadowBlur = 8; bracket(g, x0, y0, x1, y1, lw * 1.2, (x1 - x0) * 0.25); g.restore(); chip(g, x0 - 8, y0 - 34, "NGƯỜI ĐI BỘ", "#e0212f", "#fff", 15, true); }); }
      } else if (v.kind === "pole") {
        const X = 9.4;
        quad([[X - 0.2, 0, z], [X + 0.2, 0, z], [X + 0.2, 7.2, z], [X - 0.2, 7.2, z]], "#d6dde3", OUT);
        quad([[X - 0.45, 0.8, z - 0.3], [X + 0.45, 0.8, z - 0.3], [X + 0.45, 2.4, z - 0.3], [X - 0.45, 2.4, z - 0.3]], "#eef1f4", OUT);
        quad([[X - 1.4, 5.7, z - 0.3], [X - 0.2, 5.7, z - 0.3], [X - 0.2, 5.8, z - 0.3], [X - 1.4, 5.8, z - 0.3]], "#9aa4ad");
        const hx0 = X - 1.9, hx1 = X - 0.9;
        quad([[hx0, 5.0, z - 0.4], [hx1, 5.0, z - 0.4], [hx1, 6.2, z - 0.4], [hx0, 6.2, z - 0.4]], "#e2e7eb", "rgba(0,0,0,.3)");
        for (const [yy, rr] of [[5.8, 0.2], [5.35, 0.14]]) { const [lx, ly] = P(X - 1.4, yy, z - 0.45), r = Math.max(1, rr * f / z); g.fillStyle = "#101418"; g.beginPath(); g.arc(lx, ly, r, 0, 6.3); g.fill(); g.fillStyle = "#2b3d55"; g.beginPath(); g.arc(lx, ly, r * 0.55, 0, 6.3); g.fill(); }
        if (hud && z > 9 && z < 120) { const [x0, y0] = P(hx0 - 0.15, 6.35, z - 0.4), [x1, y1] = P(hx1 + 0.15, 4.85, z - 0.4); hud.push(() => { g.save(); g.strokeStyle = "#ff3344"; g.shadowColor = "#ff3344"; g.shadowBlur = 10; bracket(g, x0, y0, x1, y1, lw * 1.3, (x1 - x0) * 0.25); g.restore(); chip(g, x0 - 4, y0 - 36, "PHẠT NGUỘI", "#e0212f", "#fff", 15, true); g.strokeStyle = "#ff3344"; g.lineWidth = lw * 1.2; for (let k = 0; k < 3; k++) { const ph = (st.t * 0.9 + k / 3) % 1, r = (x1 - x0) * (0.5 + ph * 0.9); g.globalAlpha = 1 - ph; g.beginPath(); g.arc(x1, (y0 + y1) / 2, r, -0.8, 0.8); g.stroke(); } g.globalAlpha = 1; }); }
      }
    }
    g.globalAlpha = 1;
  }
  function drawCar(quad, X, Zc, col, braking, lw0) {
    const lw = lw0 * 0.6, OUT = "rgba(0,0,0,.28)";
    const Zr = Zc - 2.2, Zf = Zc + 2.2, dark = "#12171d", glass = "#2c4660", side = X > 0.3 ? X - 0.9 : X < -0.3 ? X + 0.9 : null, cside = X > 0.3 ? X - 0.78 : X < -0.3 ? X + 0.78 : null;
    for (const s of [-1, 1]) quad([[X + s * 0.45, 0, Zr], [X + s * 0.85, 0, Zr], [X + s * 0.85, 0.38, Zr], [X + s * 0.45, 0.38, Zr]], dark);
    if (side !== null) quad([[side, 0.28, Zr], [side, 0.28, Zf], [side, 0.85, Zf], [side, 0.85, Zr]], tint(col, 0.78), OUT, lw);
    quad([[X - 0.9, 0.85, Zr], [X + 0.9, 0.85, Zr], [X + 0.9, 0.85, Zf], [X - 0.9, 0.85, Zf]], tint(col, 1.12), OUT, lw);
    quad([[X - 0.9, 0.28, Zr], [X + 0.9, 0.28, Zr], [X + 0.9, 0.85, Zr], [X - 0.9, 0.85, Zr]], tint(col, 1), OUT, lw);
    const c0 = Zr + 1.0, c1 = Zf - 1.4;
    if (cside !== null) quad([[cside, 0.85, c0], [cside, 0.85, c1], [cside, 1.38, c1 - 0.5], [cside, 1.38, c0 + 0.7]], glass, OUT, lw);
    quad([[X - 0.7, 1.38, c0 + 0.7], [X + 0.7, 1.38, c0 + 0.7], [X + 0.7, 1.38, c1 - 0.5], [X - 0.7, 1.38, c1 - 0.5]], tint(col, 1.18), OUT, lw);
    quad([[X - 0.78, 0.85, c0], [X + 0.78, 0.85, c0], [X + 0.7, 1.38, c0 + 0.7], [X - 0.7, 1.38, c0 + 0.7]], glass, OUT, lw);
    for (const s of [-1, 1]) quad([[X + s * 0.5, 0.6, Zr], [X + s * 0.85, 0.6, Zr], [X + s * 0.85, 0.76, Zr], [X + s * 0.5, 0.76, Zr]], braking ? "#ff7a86" : "#e08088", OUT, lw * 0.6);
    quad([[X - 0.28, 0.36, Zr], [X + 0.28, 0.36, Zr], [X + 0.28, 0.5, Zr], [X - 0.28, 0.5, Zr]], "#f6f6f0", OUT, lw * 0.5);
  }

  // ---------- nội thất: ảnh buồng lái low-poly, khoét kính chắn gió để cảnh 3D chạy phía sau ----------
  let dash, wheel;
  const path = (g, pts) => { g.beginPath(); pts.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.closePath(); };
  async function buildInterior() {
    const img = new Image(); img.src = PHOTO; await img.decode();
    const photo = document.createElement("canvas"); photo.width = W; photo.height = H; photo.getContext("2d").drawImage(img, 0, 0, W, H);
    // vô lăng = mọi thứ trong vành, trừ phần cụm đồng hồ nhìn qua khe phía trên
    wheel = document.createElement("canvas"); wheel.width = W; wheel.height = H;
    const wx = wheel.getContext("2d"); wx.drawImage(photo, 0, 0);
    wx.globalCompositeOperation = "destination-in"; wx.beginPath(); wx.ellipse(RIM.cx, RIM.cy, RIM.rx, RIM.ry, 0, 0, Math.PI * 2); wx.fill();
    wx.globalCompositeOperation = "destination-out"; wx.filter = "blur(4px)"; path(wx, OPENING); wx.fill(); wx.filter = "none";
    // lớp tĩnh: ảnh; sau vô lăng là bản mờ tối (chỉ lộ ra khi vô lăng xoay), kính chắn gió khoét trống, gương chiếu hậu giữ lại
    dash = document.createElement("canvas"); dash.width = W; dash.height = H;
    const g = dash.getContext("2d"); g.drawImage(photo, 0, 0);
    g.save(); g.beginPath(); g.ellipse(RIM.cx, RIM.cy, RIM.rx, RIM.ry, 0, 0, Math.PI * 2); g.clip(); g.filter = "blur(22px) brightness(.55)"; g.drawImage(photo, 0, 0); g.restore();
    g.save(); path(g, OPENING); g.clip(); g.drawImage(photo, 0, 0); g.restore();
    g.globalCompositeOperation = "destination-out"; g.filter = "blur(1px)"; path(g, WINDSHIELD); g.fill(); g.filter = "none"; g.globalCompositeOperation = "source-over";
    const [mx, my, mw, mh] = MIRROR, src = photo.getContext("2d").getImageData(mx, my, mw, mh), out = g.getImageData(mx, my, mw, mh), s = src.data, o = out.data;
    for (let i = 0; i < s.length; i += 4) {   // gương: điểm tối hơn bầu trời; mép chuyển dần cho khỏi răng cưa
      const lum = 0.3 * s[i] + 0.59 * s[i + 1] + 0.11 * s[i + 2], a = Math.max(0, Math.min(1, (165 - lum) / 30));
      if (a > o[i + 3] / 255) { o[i] = s[i]; o[i + 1] = s[i + 1]; o[i + 2] = s[i + 2]; o[i + 3] = a * 255; }
    }
    g.putImageData(out, mx, my);
  }

  let t = 0, last = null, started = false, flash = 0, angle = 0, slide = 0, calm = 0, travelled = 0;
  // vô lăng như lò xo giảm chấn: vượt nhẹ rồi ổn định, như tay chỉnh lái
  const SPRING = { k: 34, c: 8.5 };
  let target = 0, steer = 0, vel = 0;
  let clean = null;                                  // nguồn nền cho hiệu ứng vào: chính canvas buồng lái
  function drawView() {
    const st = { d: travelled, t, pan: -angle * 70, sway: angle * 0.5 };
    ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W, WS.h); ctx.clip();
    const hud = []; renderWorld(ctx, WS, st, hud); hud.forEach((fn) => fn()); ctx.restore();
    // màn hình trung tâm: cùng cảnh, camera cao hơn, độ phân giải ×4 để phóng to vẫn nét; vùng đỏ trước xe là cảnh báo va chạm
    const [, , vw, vh] = SCREEN.view;
    sctx.setTransform(4, 0, 0, 4, 0, 0); sctx.clearRect(0, 0, vw, vh);
    renderWorld(sctx, SV, { ...st, pan: st.pan * 0.3 }, null);
    const k = 1 - calm, pulse = 0.5 + 0.5 * Math.sin(t * 6.2);
    if (k > 0) {
      const fl = sctx.createLinearGradient(0, 76, 0, vh); fl.addColorStop(0, `rgba(255,40,40,${(0.45 + 0.25 * pulse) * k})`); fl.addColorStop(1, `rgba(255,30,30,${(0.25 + 0.15 * pulse) * k})`);
      sctx.fillStyle = fl; sctx.beginPath(); sctx.moveTo(122, 76); sctx.lineTo(230, 76); sctx.lineTo(292, vh); sctx.lineTo(64, vh); sctx.closePath(); sctx.fill();
      const rg = sctx.createRadialGradient(176, 100, 4, 176, 100, 110); rg.addColorStop(0, `rgba(255,40,30,${0.3 * pulse * k})`); rg.addColorStop(1, "rgba(255,40,30,0)");
      sctx.fillStyle = rg; sctx.fillRect(0, 0, vw, vh);
    }
  }
  function frame(now) {
    const dt = last === null ? 0 : Math.min(0.05, (now - last) / 1000); last = now;
    if (!REDUCED) t += dt;
    flash = Math.max(0, flash - dt * 0.8);
    if (!REDUCED) for (let k = 0; k < 4; k++) { const h = dt / 4; vel += (SPRING.k * (target - steer) - SPRING.c * vel) * h; steer += vel * h; }
    else steer = target;
    const sway = REDUCED || started ? 0 : 0.014 * Math.sin(t * 0.73) + 0.007 * Math.sin(t * 1.9 + 1); // chỉnh lái nhỏ khi chạy đều
    angle = steer + sway;
    engine.update();
    if (!REDUCED) travelled += CRUISE * dt;
    drawView();
    ctx.drawImage(dash, 0, 0);

    // vô lăng (lấy từ ảnh, cả chữ V): xoay trong mặt phẳng của nó, có phối cảnh
    const turnTo = (a) => { ctx.translate(RIM.cx, RIM.cy); ctx.scale(1, RIM.ry / RIM.rx); ctx.rotate(a); ctx.scale(1, RIM.rx / RIM.ry); ctx.translate(-RIM.cx, -RIM.cy); };
    if (Math.abs(vel) > 0.35) { // nhoè chuyển động khi vô lăng quay nhanh
      for (const [lag, alpha] of [[0.05, 0.22], [0.025, 0.3]]) { ctx.save(); ctx.globalAlpha = alpha; turnTo(angle - vel * lag); ctx.drawImage(wheel, 0, 0); ctx.restore(); }
    }
    ctx.save(); turnTo(angle); ctx.drawImage(wheel, 0, 0); ctx.restore();
    if (!started && !REDUCED) { // vòng mời bấm quanh chữ V
      const p = (t * 0.55) % 1; ctx.strokeStyle = `rgba(70,214,230,${0.7 * (1 - p)})`; ctx.lineWidth = 2.5;
      ctx.beginPath(); ctx.ellipse(LOGO.cx, LOGO.cy, 62 + p * 36, 56 + p * 32, 0, 0, Math.PI * 2); ctx.stroke();
    }
    requestAnimationFrame(frame);
  }
  async function init() { await buildInterior(); clean = cv; $("loading").hidden = true; requestAnimationFrame(frame); }

  /* engine sound, synthesised: firing pulses of a 4-cylinder engine, intake noise, road and wind */
  let actx = null;
  const engine = (() => {
    let on = false, nodes = null, rpm = 1900, rev = 0, wantSound = false; // sound switched off for the demo
    function build() {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)();
      const A = actx, out = A.createGain(); out.gain.value = 0;
      const comp = A.createDynamicsCompressor(); out.connect(comp).connect(A.destination);
      const noiseBuf = A.createBuffer(1, A.sampleRate * 2, A.sampleRate), nd = noiseBuf.getChannelData(0);
      let b0 = 0; for (let i = 0; i < nd.length; i++) { b0 = 0.97 * b0 + 0.03 * (Math.random() * 2 - 1); nd[i] = b0 * 6; } // brown-ish noise
      const noise = () => { const src = A.createBufferSource(); src.buffer = noiseBuf; src.loop = true; src.start(); return src; };
      // combustion: saw + sub square through a resonant lowpass
      const saw = A.createOscillator(); saw.type = "sawtooth";
      const sub = A.createOscillator(); sub.type = "square";
      const lp = A.createBiquadFilter(); lp.type = "lowpass"; lp.Q.value = 2.2;
      const body = A.createGain(); body.gain.value = 0.22;
      const subG = A.createGain(); subG.gain.value = 0.35;
      saw.connect(lp); sub.connect(subG).connect(lp); lp.connect(body).connect(out);
      // intake rumble, amplitude pulsed at the firing rate
      const puff = noise(), bp = A.createBiquadFilter(); bp.type = "bandpass"; bp.Q.value = 0.9;
      const puffG = A.createGain(); puffG.gain.value = 0;
      const pulse = A.createOscillator(); pulse.type = "sine"; const pulseDepth = A.createGain(); pulseDepth.gain.value = 0.05;
      pulse.connect(pulseDepth).connect(puffG.gain); puff.connect(bp).connect(puffG).connect(out);
      // road and wind at 68 km/h
      const road = noise(), rlp = A.createBiquadFilter(); rlp.type = "lowpass"; rlp.frequency.value = 520;
      const roadG = A.createGain(); roadG.gain.value = 0.09; road.connect(rlp).connect(roadG).connect(out);
      const wind = noise(), whp = A.createBiquadFilter(); whp.type = "bandpass"; whp.frequency.value = 1400; whp.Q.value = 0.4;
      const windG = A.createGain(); windG.gain.value = 0.018; wind.connect(whp).connect(windG).connect(out);
      [saw, sub, pulse].forEach((o) => o.start());
      nodes = { out, saw, sub, lp, bp, pulse, puffG };
    }
    function apply() {
      const fire = rpm / 30, n = nodes, ts = actx.currentTime;
      n.saw.frequency.setTargetAtTime(fire, ts, 0.08); n.sub.frequency.setTargetAtTime(fire / 2, ts, 0.08); n.pulse.frequency.setTargetAtTime(fire, ts, 0.08);
      n.lp.frequency.setTargetAtTime(180 + rpm * 0.16 + rev * 500, ts, 0.1); n.bp.frequency.setTargetAtTime(220 + rpm * 0.1, ts, 0.1);
      n.puffG.gain.setTargetAtTime(0.05 + rev * 0.06, ts, 0.1);
    }
    return {
      get enabled() { return wantSound; },
      ensure() {
        if (!wantSound) return;
        try { if (!nodes) build(); if (actx.state === "suspended") actx.resume(); nodes.out.gain.setTargetAtTime(0.55, actx.currentTime, 0.6); on = true; } catch (e) { on = false; }
      },
      mute(m) { wantSound = !m; if (nodes) nodes.out.gain.setTargetAtTime(m ? 0 : 0.55, actx.currentTime, 0.15); if (!m) this.ensure(); },
      rev(x) { rev = x; },
      quiet(q) { if (nodes && wantSound) nodes.out.gain.setTargetAtTime(q ? 0 : 0.55, actx.currentTime, q ? 0.4 : 0.6); },
      blip() { // throttle blip on start: rpm jumps, the engine gets louder for a moment
        if (!on || !wantSound) return;
        rev = 1.8; const g = nodes.out.gain, ts = actx.currentTime;
        g.cancelScheduledValues(ts); g.setTargetAtTime(0.95, ts, 0.05); g.setTargetAtTime(0.55, ts + 0.7, 0.35);
      },
      update() { // every frame: rpm follows the throttle with lag, plus a slow wander
        if (!on) return;
        const goal = 1900 + rev * 1100 + Math.sin(performance.now() / 900) * 40;
        rpm += (goal - rpm) * 0.06; apply();
      },
      steer(gain = 0.22) { // hands sliding on the leather rim: a short, soft swish
        if (!on || !wantSound) return;
        const A = actx, ts = A.currentTime, len = Math.floor(A.sampleRate * 0.45);
        const b = A.createBuffer(1, len, A.sampleRate), d = b.getChannelData(0);
        for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (0.6 + 0.4 * Math.sin(i / 90)); // slight grain of the leather
        const src = A.createBufferSource(); src.buffer = b;
        const bp = A.createBiquadFilter(); bp.type = "bandpass"; bp.Q.value = 1.4;
        bp.frequency.setValueAtTime(700, ts); bp.frequency.exponentialRampToValueAtTime(1500, ts + 0.18); bp.frequency.exponentialRampToValueAtTime(900, ts + 0.4);
        const g = A.createGain(); g.gain.setValueAtTime(0, ts); g.gain.linearRampToValueAtTime(gain, ts + 0.06); g.gain.exponentialRampToValueAtTime(0.001, ts + 0.42);
        src.connect(bp).connect(g).connect(A.destination); src.start(ts); src.stop(ts + 0.45);
      },
    };
  })();

  /* original music for the entrance: a rising pad and pulse from the V press, a drop when the intro starts, a final chord at its end */
  const music = (() => {
    let A = null, bus = null, pad = [], padF = null, padG = null, riser = null, kicks = null;
    const note = (n) => 440 * Math.pow(2, (n - 69) / 12); // MIDI note -> Hz
    function kick(at, gain = 0.9) {
      const o = A.createOscillator(), g = A.createGain();
      o.frequency.setValueAtTime(130, at); o.frequency.exponentialRampToValueAtTime(42, at + 0.22);
      g.gain.setValueAtTime(gain, at); g.gain.exponentialRampToValueAtTime(0.001, at + 0.32);
      o.connect(g).connect(bus); o.start(at); o.stop(at + 0.34);
    }
    function pluck(freq, at, dur = 0.22, gain = 0.16, type = "triangle") {
      const o = A.createOscillator(), f = A.createBiquadFilter(), g = A.createGain();
      o.type = type; o.frequency.value = freq; f.type = "lowpass"; f.frequency.setValueAtTime(4200, at); f.frequency.exponentialRampToValueAtTime(700, at + dur);
      g.gain.setValueAtTime(0, at); g.gain.linearRampToValueAtTime(gain, at + 0.008); g.gain.exponentialRampToValueAtTime(0.001, at + dur);
      o.connect(f).connect(g).connect(bus); o.start(at); o.stop(at + dur + 0.02);
    }
    function noiseBurst(at, dur, from, to, gain) {
      const len = Math.floor(A.sampleRate * dur), b = A.createBuffer(1, len, A.sampleRate), d = b.getChannelData(0);
      for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
      const src = A.createBufferSource(), f = A.createBiquadFilter(), g = A.createGain();
      src.buffer = b; f.type = "highpass"; f.frequency.setValueAtTime(from, at); f.frequency.exponentialRampToValueAtTime(to, at + dur);
      g.gain.setValueAtTime(gain[0], at); g.gain.linearRampToValueAtTime(gain[1], at + dur * 0.92); g.gain.linearRampToValueAtTime(0, at + dur);
      src.connect(f).connect(g).connect(bus); src.start(at); src.stop(at + dur);
      return { src, g };
    }
    return {
      start(ctxA) { // at the V press
        A = ctxA; const t0 = A.currentTime;
        bus = A.createGain(); bus.gain.value = 0.8; bus.connect(A.destination);
        padF = A.createBiquadFilter(); padF.type = "lowpass"; padF.Q.value = 3; padF.frequency.setValueAtTime(260, t0); padF.frequency.exponentialRampToValueAtTime(2400, t0 + 3.8);
        padG = A.createGain(); padG.gain.setValueAtTime(0, t0); padG.gain.linearRampToValueAtTime(0.09, t0 + 1.2);
        padF.connect(padG).connect(bus);
        pad = [45, 52, 57, 60, 64].flatMap((n) => [-6, 6].map((cents) => { // A minor add9, two detuned saws per voice
          const o = A.createOscillator(); o.type = "sawtooth"; o.frequency.value = note(n); o.detune.value = cents; o.connect(padF); o.start(t0); return o;
        }));
        riser = noiseBurst(t0 + 0.4, 3.5, 400, 7000, [0, 0.12]);
        let k = 0; kicks = setInterval(() => { kick(A.currentTime + 0.02, 0.35 + Math.min(0.4, k * 0.05)); k++; }, 480);
      },
      drop() { // at the start of the 3 s intro: the music settles down and is gone exactly 3 s later
        if (!A) return; const t = A.currentTime + 0.02, end = t + 3;
        clearInterval(kicks);
        if (riser) { riser.g.gain.cancelScheduledValues(t); riser.g.gain.setValueAtTime(riser.g.gain.value, t); riser.g.gain.linearRampToValueAtTime(0, t + 0.8); }
        bus.gain.cancelScheduledValues(t); bus.gain.setValueAtTime(bus.gain.value, t);
        bus.gain.linearRampToValueAtTime(0.42, t + 1.2); bus.gain.linearRampToValueAtTime(0.28, end - 0.4); bus.gain.linearRampToValueAtTime(0, end);
        [0, 0.94].forEach((dt, i) => kick(t + dt, 0.45 - i * 0.2));      // two soft beats, then none
        const arp = [69, 72, 76, 81, 76, 72, 69, 64];                     // slower, falling A minor line
        arp.forEach((n, i) => pluck(note(n), t + 0.15 + i * 0.234, 0.5, 0.07 - i * 0.005));
        [57, 64, 69, 72].forEach((n) => pluck(note(n), t + 2.0, 1.0, 0.05, "sine")); // quiet closing chord as the V appears
        padF.frequency.cancelScheduledValues(t); padF.frequency.setValueAtTime(padF.frequency.value, t); padF.frequency.exponentialRampToValueAtTime(500, end);
        padG.gain.cancelScheduledValues(t); padG.gain.setValueAtTime(padG.gain.value, t); padG.gain.linearRampToValueAtTime(0, end);
        pad.forEach((o) => o.stop(end + 0.05));
      },
      stop() { // cut short (Escape / back)
        if (!A || !bus) return; clearInterval(kicks); const t = A.currentTime;
        bus.gain.cancelScheduledValues(t); bus.gain.setTargetAtTime(0, t, 0.05); pad.forEach((o) => { try { o.stop(t + 0.3); } catch (e) {} });
        if (riser) try { riser.src.stop(t + 0.3); } catch (e) {}
        A = null;
      },
    };
  })();

  /* the entrance: the RoadWatch V appears on the dark screen with its name, then fades into the app */
  function playIntro(ms) {
    return new Promise((done) => {
      const c = $("intro"); c.hidden = false;
      const x = c.getContext("2d"), dpr = Math.min(2, devicePixelRatio || 1);
      c.width = innerWidth * dpr; c.height = innerHeight * dpr; x.setTransform(dpr, 0, 0, dpr, 0, 0);
      const END = 0;
      // background: the main photo, covering the screen, blurred once up front
      let bg = null;
      if (clean) {
        bg = document.createElement("canvas"); bg.width = innerWidth; bg.height = innerHeight;
        // nền: màn hình trung tâm, đúng khung hình nơi hiệu ứng vào vừa dừng, làm mờ
        const b = bg.getContext("2d"), k = screenScale();
        b.filter = "blur(14px) brightness(.62) saturate(.9)";
        const ox = innerWidth / 2 - SCREEN.cx * k, oy = innerHeight / 2 - SCREEN.cy * k;
        b.drawImage(clean, ox, oy, W * k, H * k);
        b.drawImage(cvs, ox + SCREEN.view[0] * k, oy + SCREEN.view[1] * k, SCREEN.view[2] * k, SCREEN.view[3] * k);
        b.filter = "none"; b.fillStyle = "rgba(15,21,28,.22)"; b.fillRect(0, 0, innerWidth, innerHeight);
      }
      const t0 = performance.now();
      const step = (now) => {
        const p = Math.min(1, (now - t0) / ms), w = innerWidth, h = innerHeight;
        x.fillStyle = "#0f151c"; x.fillRect(0, 0, w, h);
        if (bg) x.drawImage(bg, 0, 0, w, h);                 // the cockpit photo, blurred and dimmed, behind the V
        if (p > END) {
          const qv = Math.min(1, (p - END) / 0.3), grow = 0.35 + 0.65 * (1 - Math.pow(1 - qv, 3));
          const size = Math.min(w, h) * 0.16 * grow, vx = w / 2, vy = h * 0.42;
          x.save(); x.globalAlpha = qv; x.lineCap = "round"; x.lineJoin = "round";
          const g = x.createLinearGradient(vx - size, vy - size, vx + size, vy + size); g.addColorStop(0, "#f6f8fa"); g.addColorStop(0.5, "#9aa3ad"); g.addColorStop(1, "#e2e7ec");
          x.shadowColor = "#46d6e6"; x.shadowBlur = 30; x.strokeStyle = g; x.lineWidth = size * 0.13;
          x.beginPath(); x.moveTo(vx - size * 0.62, vy - size * 0.55); x.lineTo(vx, vy + size * 0.6); x.lineTo(vx + size * 0.62, vy - size * 0.55); x.stroke();
          x.strokeStyle = "#46d6e6"; x.lineWidth = size * 0.045;
          x.beginPath(); x.moveTo(vx - size * 0.26, vy - size * 0.55); x.lineTo(vx, vy - size * 0.06); x.lineTo(vx + size * 0.26, vy - size * 0.55); x.stroke();
          x.restore();
          const tq = Math.max(0, Math.min(1, (p - END - 0.18) / 0.25)), fs = Math.min(w, h) * 0.16;
          x.globalAlpha = tq; x.textAlign = "center"; x.textBaseline = "middle"; x.fillStyle = "#e8eef4";
          x.shadowColor = "rgba(0,0,0,.6)"; x.shadowBlur = 12;
          x.font = `700 ${Math.round(fs * 0.34)}px 'Be Vietnam Pro', system-ui, sans-serif`;
          x.fillText("RoadWatch Copilot", vx, vy + fs * 0.95 + (1 - tq) * 12);
          x.fillStyle = "#a9c4dc"; x.font = `400 ${Math.round(fs * 0.15)}px 'JetBrains Mono', ui-monospace, monospace`;
          x.fillText("GIỮ KHOẢNG CÁCH · NHẮC ĐÚNG LÚC", vx, vy + fs * 1.32 + (1 - tq) * 12);
          x.globalAlpha = 1; x.shadowBlur = 0;
        }
        if (p > 0.82) { x.fillStyle = `rgba(15,21,28,${(p - 0.82) / 0.18})`; x.fillRect(0, 0, w, h); }
        if (p < 1) requestAnimationFrame(step); else done();
      };
      requestAnimationFrame(step);
    });
  }
  addEventListener("pointerdown", () => engine.ensure(), { once: true });
  addEventListener("keydown", () => engine.ensure(), { once: true });

  /* start sequence: chime, then zoom into the center screen */
  function chime() {
    try {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)();
      [523.25, 659.25, 783.99].forEach((f, i) => {
        const o = actx.createOscillator(), g = actx.createGain(), s = actx.currentTime + i * 0.12;
        o.frequency.value = f; g.gain.setValueAtTime(0, s); g.gain.linearRampToValueAtTime(0.12, s + 0.02); g.gain.exponentialRampToValueAtTime(0.001, s + 0.6);
        o.connect(g).connect(actx.destination); o.start(s); o.stop(s + 0.62);
      });
    } catch (e) { /* sound is optional */ }
  }
  const TURN = 0.4; // radians, about 23 degrees to the right: a lane change
  // Hiệu ứng vào: phóng to vào màn hình trung tâm (đang cảnh báo khoảng cách) cho tới khi nó phủ kín khung nhìn;
  // xe phía trước đứng yên, vô lăng và táp-lô trôi ra ngoài khung.
  const screenScale = () => Math.min(innerWidth / SCREEN.w, innerHeight / SCREEN.h) * 1.04;   // ảnh px -> px màn hình khi dừng
  function zoom(on) {
    const stage = $("stage");
    if (!on) { stage.style.transition = ""; stage.style.transform = ""; stage.style.filter = ""; return; }
    const r = stage.getBoundingClientRect(), k = r.width / W;
    const ox = SCREEN.cx * k, oy = SCREEN.cy * k;
    stage.style.transition = "transform 1.6s cubic-bezier(.65,0,.35,1), filter 1.6s ease-in";
    stage.style.transformOrigin = `${ox}px ${oy}px`;
    stage.style.transform = `translate(${innerWidth / 2 - (r.left + ox)}px, ${innerHeight / 2 - (r.top + oy)}px) scale(${screenScale() / k})`;
    stage.style.filter = "brightness(1.08)";
  }
  const account = document.querySelector('nav[aria-label="Tài khoản"]');
  const wait = (ms) => new Promise((r) => setTimeout(r, REDUCED ? 0 : ms));
  async function start() {
    if (started || !clean) return; started = true; flash = 0.9;
    $("stage").classList.add("go"); account.style.visibility = "hidden";   // nút tài khoản không trôi theo hiệu ứng vào
    zoom(true);                                      // into the center screen, its collision alert still pulsing
    await wait(1600);
    await wait(150);
    if (!started) return;                            // left early with Escape
    await playIntro(1600);
    if (!started) return;
    location.href = ENTER_URL;
  }
  function back() {   // Escape giữa hiệu ứng vào: quay lại buồng lái
    zoom(false); $("intro").hidden = true; account.style.visibility = ""; music.stop();
    setTimeout(() => { slide = 0; calm = 0; target = 0; started = false; $("stage").classList.remove("go"); $("vbtn").focus(); }, REDUCED ? 0 : 1000);
  }
  $("vbtn").addEventListener("click", start);
  addEventListener("keydown", (e) => { if (e.key === "Escape" && started) { started = false; back(); } });
  // quay lại trang này bằng nút Back của trình duyệt: trang có thể lấy từ bộ nhớ đệm, đưa buồng lái về trạng thái đầu
  addEventListener("pageshow", (e) => { if (e.persisted && started) { started = false; back(); } });

  /* vô lăng: bấm vào nửa trái/phải thì đánh lái về phía đó rồi tự trả lái; giữ và kéo thì vô lăng xoay theo tay,
     thả ra thì lò xo đưa về giữa. Chữ V ở tâm vẫn là nút khởi động. */
  const MAX_TURN = 2.4;                                  // rad, khoảng 140°: giới hạn kéo tay
  const toPhoto = (e) => { const r = $("stage").getBoundingClientRect(); return [(e.clientX - r.left) * W / r.width, (e.clientY - r.top) * H / r.height]; };
  const onWheel = ([x, y]) => ((x - RIM.cx) / RIM.rx) ** 2 + ((y - RIM.cy) / RIM.ry) ** 2 <= 1;
  const handAngle = ([x, y]) => Math.atan2((y - RIM.cy) * RIM.rx / RIM.ry, x - RIM.cx);   // góc trong mặt phẳng vô lăng (bỏ phối cảnh)
  let grab = null, settle = 0;
  const wheelZone = $("wheel");
  wheelZone.addEventListener("pointerdown", (e) => {
    const p = toPhoto(e); if (!onWheel(p) || started) return;
    e.preventDefault(); wheelZone.setPointerCapture(e.pointerId); engine.ensure();
    grab = { a0: handAngle(p), s0: target, moved: false, x: e.clientX, y: e.clientY }; clearTimeout(settle);
  });
  wheelZone.addEventListener("pointermove", (e) => {
    if (!grab) { wheelZone.style.cursor = onWheel(toPhoto(e)) && !started ? "grab" : ""; return; }
    if (Math.hypot(e.clientX - grab.x, e.clientY - grab.y) > 4) grab.moved = true;
    if (!grab.moved) return;
    let d = handAngle(toPhoto(e)) - grab.a0; d = Math.atan2(Math.sin(d), Math.cos(d));
    target = Math.max(-MAX_TURN, Math.min(MAX_TURN, grab.s0 + d)); wheelZone.style.cursor = "grabbing";
  });
  const release = (e) => {
    if (!grab) return;
    const clickTurn = !grab.moved; grab = null; wheelZone.style.cursor = "";
    if (clickTurn) {                                     // bấm: đánh lái ~40° về phía đã bấm
      const [x] = toPhoto(e); target = x < RIM.cx ? -0.7 : 0.7; engine.steer();
      settle = setTimeout(() => { target = 0; engine.steer(0.12); }, 650);
    } else { target = 0; engine.steer(0.12); }        // thả tay: trả lái
  };
  wheelZone.addEventListener("pointerup", release);
  wheelZone.addEventListener("pointercancel", release);
  wheelZone.addEventListener("keydown", (e) => {        // bàn phím: mũi tên trái/phải đánh lái
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault(); clearTimeout(settle); target = e.key === "ArrowLeft" ? -0.7 : 0.7; engine.steer();
    settle = setTimeout(() => { target = 0; }, 650);
  });
  init();
})();
