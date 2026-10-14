/* Bản đồ 3D phối cảnh quanh xe: xe mình, ba làn cao tốc, xe phía trước đặt đúng khoảng cách BT-A đo được, vùng ngưỡng luật
   trên mặt đường và mức cảnh báo BT-B. Tự dựng bằng canvas 2D (chiếu phối cảnh, cắt mặt phẳng gần, vẽ từ xa tới gần):
   không thư viện, không CDN, chạy offline.

   RWScene3D.create(canvas, get, opts) -> { view(name), redraw() }
   get() trả trạng thái của khung đang xem: { ego_kmh, gap_m, thr_m, ttc_s, level, note, traffic } (giá trị thiếu là null);
   traffic (tuỳ chọn) là các xe khác: [{ lane, z }], lane từ -1 (làn trái) qua 0 (làn mình) tới 1 (làn phải), số lẻ là
   đang chuyển làn; z là khoảng cách tính từ cản trước xe mình (m).
   opts: { interactive = true, hud = true, view = "chase", theme = "dark" }; trang giới thiệu dùng theme "daylight".
   Toạ độ thế giới (m): x sang phải, y lên trên, z về phía trước; cản trước xe mình ở z = 0. */
(() => {
  "use strict";
  const sceneScriptURL = document.currentScript.src;
  const LANE = 3.5, ROAD = 1.5 * LANE, CAR = { w: 1.8, l: 4.6 };
  const LEVEL_COLOR = { info: "#2d6fd0", warning: "#c98a1c", emergency: "#e0453c" };
  const LEVEL_VI = { info: "Nhắc", warning: "Cảnh báo", emergency: "Khẩn cấp" };
  const VIEWS = { chase: { yaw: 0, pitch: 0.33, dist: 24 }, top: { yaw: 0, pitch: 1.25, dist: 46 }, side: { yaw: -1.15, pitch: 0.28, dist: 30 } };
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);
  const nf = (v, d = 1) => v.toLocaleString("vi-VN", { minimumFractionDigits: d, maximumFractionDigits: d });
  const hex = (h) => { const n = parseInt(h.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; };
  const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
  const rgb = (c, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

  function create(cv, get, opts = {}) {
    const g = cv.getContext("2d");
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const hud = opts.hud !== false, daylight = opts.theme === "daylight";
    const vf3Image = daylight ? new Image() : null;
    if (vf3Image) {
      vf3Image.onload = () => kick();
      vf3Image.src = new URL("vf3.png", sceneScriptURL).href;
    }
    const home = typeof opts.view === "object" ? opts.view : VIEWS[opts.view] || VIEWS.chase;
    const cam = { ...home }, aim = { ...home };
    let W = 0, H = 0, raf = 0, last = 0, scroll = 0, shown = { gap: null, thr: null }, visible = false, drag = null;
    let frameZ = daylight ? 13 : 8;   // hero giữ góc nhìn ổn định; các cảnh dữ liệu tự nhìn vào giữa hai xe
    const SKY = hex(daylight ? "#c9d6df" : "#0d1824"), FOG = hex(daylight ? "#d1dacb" : "#16222e");

    /* ---------- camera ---------- */
    let P, R, U, F, FOC;
    function setCamera() {
      const t = [0, 0.8, frameZ], cp = Math.cos(cam.pitch);
      // xe mình cách tâm nhìn frameZ mét: tách thành phần dọc trục nhìn (a) và vuông góc (perp), lùi camera tới khi góc lệch
      // nhỏ hơn ~12,5° (nửa trường nhìn dọc là 18°, chừa lề); khoảng cách người xem chọn (cuộn chuột) là mức tối thiểu
      const a = -frameZ * Math.cos(cam.yaw) * cp, perp = Math.sqrt(Math.max(0, frameZ * frameZ - a * a));
      const dist = Math.max(cam.dist, perp / 0.22 - a + 4);
      P = [t[0] + dist * Math.sin(cam.yaw) * cp, t[1] + dist * Math.sin(cam.pitch), t[2] - dist * Math.cos(cam.yaw) * cp];
      F = norm(sub(t, P)); R = norm(cross([0, 1, 0], F)); U = cross(F, R);
      FOC = H / (2 * Math.tan(0.5 * 0.62));              // trường nhìn dọc ~36°: xe ở xa không quá nhỏ
    }
    const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
    const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
    const norm = (a) => { const l = Math.hypot(...a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
    const toCam = (p) => { const d = sub(p, P); return [dot(d, R), dot(d, U), dot(d, F)]; };
    const NEAR = 0.4;
    const proj = (c) => [W / 2 + c[0] / c[2] * FOC, H * 0.5 - c[1] / c[2] * FOC];
    function clip(poly) {                                   // Sutherland–Hodgman với mặt phẳng gần cz = NEAR
      const out = [];
      for (let i = 0; i < poly.length; i++) {
        const a = poly[i], b = poly[(i + 1) % poly.length], ina = a[2] >= NEAR, inb = b[2] >= NEAR;
        if (ina) out.push(a);
        if (ina !== inb) { const t = (NEAR - a[2]) / (b[2] - a[2]); out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, NEAR]); }
      }
      return out;
    }

    /* ---------- polygons: ground layer first, then solids sorted far to near ---------- */
    let ground, overlay, solids, labels;
    function quad(list, pts, color, alpha = 1, fog = true) {
      const c = pts.map(toCam), cl = clip(c); if (cl.length < 3) return;
      const depth = c.reduce((s, p) => s + p[2], 0) / c.length;
      const f = fog ? Math.min(1, Math.max(0, (depth - 40) / 180)) : 0;
      list.push({ depth, pts: cl.map(proj), fill: rgb(mix(color, FOG, f), alpha) });
    }
    const flat = (x0, x1, z0, z1, y = 0) => [[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]];
    function box(cx, cz, w, l, y0, y1, color) {             // hộp thẳng trục; chỉ vẽ mặt quay về camera, tô theo hướng mặt
      const x0 = cx - w / 2, x1 = cx + w / 2, z0 = cz - l / 2, z1 = cz + l / 2;
      const faces = [
        [[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]].concat([[0, 1, 0, 1.18]]),
        [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0]].concat([[0, 0, -1, 0.95]]),
        [[x0, y0, z1], [x0, y1, z1], [x1, y1, z1], [x1, y0, z1]].concat([[0, 0, 1, 0.8]]),
        [[x0, y0, z0], [x0, y1, z0], [x0, y1, z1], [x0, y0, z1]].concat([[-1, 0, 0, 0.72]]),
        [[x1, y0, z0], [x1, y0, z1], [x1, y1, z1], [x1, y1, z0]].concat([[1, 0, 0, 0.72]]),
      ];
      const parts = [];
      for (const f of faces) {
        const [nx, ny, nz, shade] = f[4], pts = f.slice(0, 4), mid = pts.reduce((s, p) => [s[0] + p[0] / 4, s[1] + p[1] / 4, s[2] + p[2] / 4], [0, 0, 0]);
        if (dot([nx, ny, nz], sub(mid, P)) >= 0) continue;  // mặt quay lưng
        const c = pts.map(toCam), cl = clip(c); if (cl.length < 3) continue;
        parts.push({ pts: cl.map(proj), fill: rgb(color.map((v) => Math.min(255, v * shade))) });
      }
      const center = toCam([cx, (y0 + y1) / 2, cz]);
      return { depth: center[2], parts };
    }
    function car(cz, color, brake, cx = 0) {                // thân, cabin, đèn hậu; cz: tâm xe theo trục z, cx: tâm làn
      const body = box(cx, cz, CAR.w, CAR.l, 0.28, 0.95, color);
      const cabin = box(cx, cz - 0.25, CAR.w * 0.84, CAR.l * 0.5, 0.95, 1.42, mix(color, [20, 28, 36], 0.45));
      const tail = box(cx, cz - CAR.l / 2 - 0.01, CAR.w * 0.9, 0.02, 0.62, 0.78, brake ? [255, 60, 50] : [150, 40, 40]);
      const wheels = [-1, 1].flatMap((sx) => [-1, 1].map((sz) => box(cx + sx * CAR.w * 0.42, cz + sz * CAR.l * 0.3, 0.26, 0.66, 0, 0.42, [16, 18, 22])));
      return { depth: body.depth, parts: [...wheels.flatMap((b) => b.parts), ...body.parts, ...cabin.parts, ...tail.parts] };
    }
    // Xe tách nền từ ảnh tham chiếu: giữ nguyên góc và tỷ lệ, chỉ thu phóng đồng đều.
    function introVF3() {
      // Kích thước minh hoạ trong hero, không dùng cho phép đo khoảng cách.
      const front = proj(toCam([0, 0.04, -0.6]));
      const rear = proj(toCam([0, 0.04, -3.0]));
      // Khoảng cách hai bánh trái trong ảnh 1386 × 1135: (280, 690) → (615, 1055).
      const scale = Math.hypot(rear[0] - front[0], rear[1] - front[1]) / Math.hypot(335, 365) * 0.85;
      const width = vf3Image.naturalWidth * scale, height = vf3Image.naturalHeight * scale;
      const shadowCenter = proj(toCam([0, 0.02, -1.8]));
      return { depth: toCam([0, 0.8, -1.8])[2], draw() {
        g.save();
        // Bóng nằm trên mặt đường, độc lập với ảnh xe.
        const across = proj(toCam([1.0, 0.02, -1.8]));
        const along = proj(toCam([0, 0.02, 0.2]));
        g.save();
        g.transform(across[0] - shadowCenter[0], across[1] - shadowCenter[1],
          along[0] - shadowCenter[0], along[1] - shadowCenter[1], ...shadowCenter);
        const shadow = g.createRadialGradient(0, 0, 0, 0, 0, 1);
        shadow.addColorStop(0, "rgba(0,0,0,0.35)");
        shadow.addColorStop(1, "rgba(0,0,0,0)");
        g.fillStyle = shadow;
        g.beginPath(); g.arc(0, 0, 1, 0, Math.PI * 2); g.fill();
        g.restore();
        // Neo giữa hai bánh sau; tuyệt đối không kéo lệch, xoay hoặc ép tỷ lệ ảnh.
        g.drawImage(vf3Image, rear[0] - 850 * scale, rear[1] - 990 * scale, width, height);
        g.restore();
      } };
    }
    // Cây low-poly: các tam giác màu khác nhau tạo mặt sáng/tối như mô hình ADAS mẫu.
    function tree(cx, cz, radius, height, color) {
      const trunk = box(cx, cz, 0.42, 0.42, 0, height, [126, 106, 82]);
      const parts = [...trunk.parts], n = 6, cy = height + radius * 0.65;
      const rings = [[radius * 0.68, cy - radius * 0.72], [radius, cy], [radius * 0.64, cy + radius * 0.72]];
      const at = (ring, i) => {
        const a = i * Math.PI * 2 / n + ring * 0.22;
        return [cx + Math.cos(a) * rings[ring][0], rings[ring][1], cz + Math.sin(a) * rings[ring][0]];
      };
      const facet = (pts, shade) => {
        const c = pts.map(toCam), cl = clip(c); if (cl.length < 3) return;
        const depth = c.reduce((sum, p) => sum + p[2], 0) / c.length;
        const haze = Math.min(0.72, Math.max(0, (depth - 45) / 230));
        parts.push({ depth, pts: cl.map(proj), fill: rgb(mix(color.map((v) => Math.min(255, Math.round(v * shade))), FOG, haze)) });
      };
      for (let i = 0; i < n; i++) {
        const j = (i + 1) % n, shade = 0.8 + 0.32 * (1 + Math.cos(i * Math.PI * 2 / n - 0.8)) / 2;
        facet([at(0, i), at(0, j), at(1, i)], shade * 0.87);
        facet([at(0, j), at(1, j), at(1, i)], shade);
        facet([at(1, i), at(1, j), at(2, i)], shade * 1.06);
        facet([at(1, j), at(2, j), at(2, i)], shade * 1.1);
        facet([at(2, i), at(2, j), [cx, cy + radius * 1.12, cz]], shade * 1.14);
      }
      parts.sort((a, b) => b.depth - a.depth);
      return { depth: toCam([cx, cy, cz])[2], parts };
    }
    function label(p, text, color, sub2, lift = 0) { const c = toCam(p); if (c[2] > NEAR) labels.push({ at: proj(c), text, color, sub: sub2, lift }); }

    /* ---------- frame ---------- */
    function frame(now) {
      const dt = last ? Math.min(0.1, (now - last) / 1000) : 0; last = now;
      const s = get() || {};
      const ego = isNum(s.ego_kmh) ? s.ego_kmh : 0, k = 1 - Math.exp(-dt * 7);
      if (!still) scroll += ego / 3.6 * dt;
      shown.gap = isNum(s.gap_m) ? (isNum(shown.gap) && dt ? shown.gap + (s.gap_m - shown.gap) * k : s.gap_m) : null;
      shown.thr = isNum(s.thr_m) ? (isNum(shown.thr) && dt ? shown.thr + (s.thr_m - shown.thr) * k : s.thr_m) : null;
      for (const key of ["yaw", "pitch", "dist"]) cam[key] += (aim[key] - cam[key]) * (dt ? 1 - Math.exp(-dt * 6) : 1);
      const gz = isNum(shown.gap) ? shown.gap : 0, kf = dt ? 1 - Math.exp(-dt * 2) : 1;
      if (!daylight) frameZ += (Math.max(6, Math.min(50, gz * 0.5)) - frameZ) * kf;
      draw(s);
      raf = visible && !still ? requestAnimationFrame(frame) : 0;
    }
    function draw(s) {
      const dpr = daylight ? Math.min(devicePixelRatio || 1, 1.5) : devicePixelRatio || 1;
      W = cv.clientWidth; H = cv.clientHeight; if (!W || !H) return;
      if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      setCamera();
      // trời
      const sky = g.createLinearGradient(0, 0, 0, H); sky.addColorStop(0, rgb(SKY)); sky.addColorStop(1, rgb(daylight ? hex("#e5ebdf") : FOG));
      g.fillStyle = sky; g.fillRect(0, 0, W, H);
      ground = []; overlay = []; solids = []; labels = [];
      const level = s.level || null, lc = level ? hex(LEVEL_COLOR[level]) : null;
      // mặt đất, lề, mặt đường theo từng đoạn 10 m (để sương mù và cắt mặt phẳng gần đều)
      for (let z = -60; z < 260; z += 10) {
        const end = z + (daylight ? 10.06 : 10);
        quad(ground, flat(-60, -ROAD - 2, z, end), daylight ? [203, 215, 180] : [14, 22, 28]);
        quad(ground, flat(ROAD + 2, 60, z, end), daylight ? [203, 215, 180] : [14, 22, 28]);
        quad(ground, flat(-ROAD - 2, ROAD + 2, z, end), daylight ? [67, 69, 71] : [33, 41, 50]);
      }
      if (daylight) {
        for (const side of [-1, 1]) quad(ground, flat(side < 0 ? -ROAD - 2 : ROAD, side < 0 ? -ROAD : ROAD + 2, -60, 260, 0.005), [207, 211, 186]);
      }
      // vạch: hai mép liền, hai vạch chia làn đứt (dài 6 m, chu kỳ 12 m), trôi theo tốc độ xe mình
      for (const x of [-ROAD, ROAD]) for (let z = -60; z < 260; z += 20) quad(overlay, flat(x - 0.08, x + 0.08, z, z + 20, 0.01), [210, 218, 226], 0.85);
      for (const x of [-LANE / 2, LANE / 2]) for (let z = -60 - scroll % 12; z < 260; z += 12) quad(overlay, flat(x - 0.07, x + 0.07, z, z + 6, 0.01), [225, 232, 238], 0.8);
      if (daylight) {
        // Cung cảm biến vẽ trên mặt đường, chỉ là hình minh hoạ của trang giới thiệu.
        for (const center of [0, isNum(shown.gap) ? shown.gap : 26]) {
          for (const r of [4, 7, 10, 13]) for (let i = 0; i < 18; i++) {
            const a = -Math.PI * 0.76 + i * Math.PI * 1.52 / 18, b = a + Math.PI * 1.52 / 18;
            const point = (radius, angle) => [Math.sin(angle) * radius, 0.035, center + Math.cos(angle) * radius];
            quad(overlay, [point(r, a), point(r + 0.055, a), point(r + 0.055, b), point(r, b)], [154, 220, 225], 0.38, false);
          }
        }
      }
      // vùng ngưỡng luật trên làn mình (khoảng cách tối thiểu theo tốc độ hiện tại)
      if (isNum(shown.thr)) {
        const below = isNum(shown.gap) && shown.gap < shown.thr;
        quad(overlay, flat(-LANE / 2 + 0.25, LANE / 2 - 0.25, 0, shown.thr, 0.02), below ? [224, 140, 30] : [200, 150, 40], below ? 0.3 : 0.16, false);
        quad(overlay, flat(-LANE / 2 + 0.25, LANE / 2 - 0.25, shown.thr - 0.4, shown.thr, 0.03), [232, 170, 50], 0.95, false);
      }
      // hộ lan và cột bên đường (cảnh nền, trôi theo tốc độ)
      for (const x of [-ROAD - 1.6, ROAD + 1.6]) {
        if (!daylight) for (let z = -60; z < 260; z += 10) solids.push(box(x, z + 5, 0.15, 10, 0.5, 0.85, [120, 132, 144]));
        for (let z = -48 - scroll % (daylight ? 7 : 24); z < 260; z += daylight ? 7 : 24) solids.push(box(x + Math.sign(x) * 0.4, z, daylight ? 0.09 : 0.18, 0.12, 0, daylight ? 0.7 : 1.3, daylight ? [142, 148, 145] : [90, 100, 110]));
      }
      if (daylight) {
        const greens = [[143, 177, 118], [169, 195, 139], [120, 161, 106], [185, 205, 151]];
        for (const side of [-1, 1]) {
          const first = Math.floor(scroll / 11) - 5;
          for (let i = first; i < first + 30; i++) {
            const z = i * 11 - scroll;
            if (z < -38 || z > 190) continue;
            const v = Math.sin(i * 78.23 + side * 32.7) * 43758.5453, u = v - Math.floor(v);
            const x = side * (11 + u * 4), r = 2.7 + u * 1.6;
            solids.push(tree(x, z, r, 2.3 + u * 1.8, greens[((i + (side + 1) * 2) % greens.length + greens.length) % greens.length]));
            if (i % 2 === 0) solids.push(tree(side * (17 + u * 7), z + 5, r * 1.12, 2.8 + u * 2, greens[((i + 1 + (side + 1) * 2) % greens.length + greens.length) % greens.length]));
          }
        }
        for (let z = -35 - scroll % 48; z < 260; z += 48) {
          const x = ROAD + 2.4;
          solids.push(box(x, z, 0.12, 0.12, 0, 9.5, [150, 159, 157]));
          solids.push(box(x - 1.1, z, 2.3, 0.12, 9.3, 9.45, [150, 159, 157]));
          solids.push(box(x - 2.1, z, 0.6, 0.35, 9.15, 9.35, [228, 229, 204]));
        }
        const signZ = 165 - scroll % 240;
        for (const x of [-ROAD - 2, ROAD + 2]) solids.push(box(x, signZ, 0.15, 0.15, 0, 8.2, [151, 159, 157]));
        solids.push(box(0, signZ, ROAD * 2 + 4, 0.15, 8, 8.18, [151, 159, 157]));
        for (const x of [-2.3, 2.3]) {
          solids.push(box(x, signZ - 0.12, 3.9, 0.12, 6.3, 7.9, [24, 126, 63]));
          solids.push(box(x, signZ - 0.2, 2.8, 0.03, 7.27, 7.35, [230, 239, 225]));
          solids.push(box(x, signZ - 0.2, 2.2, 0.03, 6.77, 6.85, [230, 239, 225]));
        }
      }
      // xe khác trên đường (chỉ vẽ, không đo)
      for (const t of Array.isArray(s.traffic) ? s.traffic : []) if (isNum(t.z) && isNum(t.lane) && Math.abs(t.lane) <= 1) solids.push(car(t.z + CAR.l / 2, daylight ? [174, 181, 181] : [84, 96, 110], false, t.lane * LANE));
      // xe mình (cản trước ở z = 0)
      solids.push(daylight && vf3Image.complete && vf3Image.naturalWidth ? introVF3() : car(-CAR.l / 2, [11, 135, 151], false));
      // xe phía trước: chỉ khi BT-A đo được khoảng cách
      if (isNum(shown.gap)) {
        const z = shown.gap, col = lc || (daylight ? [172, 181, 183] : [92, 108, 124]), closing = isNum(s.ttc_s);
        const mark = lc || [70, 214, 230];
        quad(overlay, flat(-LANE / 2 + 0.15, LANE / 2 - 0.15, z - 1, z + CAR.l + 1, 0.02), mark, daylight ? 0.17 : 0.32, false);   // ô đánh dấu dưới xe trước
        if (!daylight) quad(overlay, flat(-0.09, 0.09, 0.2, Math.max(0.3, z - 0.2), 0.04), mark, 0.95, false);       // dây đo khoảng cách
        solids.push(car(z + CAR.l / 2, col, closing));
        label([0, 1.45, z + CAR.l / 2], daylight ? `XE PHÍA TRƯỚC · ${nf(isNum(s.gap_m) ? s.gap_m : z, 0)} m` : `${nf(isNum(s.gap_m) ? s.gap_m : z)} m`, lc ? LEVEL_COLOR[level] : "#46d6e6",
          isNum(s.ttc_s) ? `TTC ${nf(s.ttc_s)} s` : null, 30);
      }
      if (isNum(shown.thr)) label([ROAD + 2.5, 0.2, shown.thr], `ngưỡng ${nf(shown.thr, 0)} m`, "#e8b04a");   // sau nhãn khoảng cách: nhường chỗ
      // vẽ
      for (const layer of [ground, overlay]) { layer.sort((a, b) => b.depth - a.depth); for (const q of layer) poly(q.pts, q.fill); }
      solids.sort((a, b) => b.depth - a.depth);
      for (const o of solids) {
        if (o.draw) o.draw();
        else for (const p of o.parts) poly(p.pts, p.fill);
      }
      g.font = "600 12px ui-monospace, Consolas, monospace"; g.textAlign = "center"; g.textBaseline = "middle";
      const placed = [];
      for (const l of labels) {
        const w = g.measureText(l.text).width + 14, x = l.at[0];
        let y = l.at[1] - l.lift;
        for (let k = 0; k < 6 && placed.some((r) => Math.abs(r.x - x) < (r.w + w) / 2 + 4 && Math.abs(r.y - y) < 26); k++) y += 26;   // không đè nhãn trước
        placed.push({ x, y, w });
        if (l.lift) { g.strokeStyle = l.color; g.lineWidth = 1.5; g.beginPath(); g.moveTo(x, y + 11); g.lineTo(x, l.at[1]); g.stroke(); }
        g.fillStyle = "rgba(8,12,18,.78)"; g.strokeStyle = l.color; g.lineWidth = 1.5;
        g.beginPath(); g.roundRect(x - w / 2, y - 11, w, 22, 11); g.fill(); g.stroke();
        g.fillStyle = l.color; g.fillText(l.text, x, y + 0.5);
        if (l.sub) { g.font = "11px ui-monospace, Consolas, monospace"; g.fillStyle = "#c9d4de"; g.fillText(l.sub, x, y - 20); g.font = "600 12px ui-monospace, Consolas, monospace"; }
      }
      // khung chữ góc: tốc độ, mức cảnh báo, ghi chú
      if (!hud) return;
      g.textAlign = "left"; g.font = "12px ui-monospace, Consolas, monospace";
      g.fillStyle = "#c9d4de"; g.fillText(isNum(s.ego_kmh) ? `Xe mình ${nf(s.ego_kmh, 0)} km/h` : "Xe mình —", 12, 18);
      if (level) { g.fillStyle = LEVEL_COLOR[level]; g.font = "700 12px system-ui, sans-serif"; g.fillText(`● ${LEVEL_VI[level]}`, 12, 36); }
      const note = s.note || (isNum(shown.gap) ? null : "Không thấy xe phía trước đủ tin cậy");
      if (note) { g.fillStyle = "#8d99a6"; g.font = "12px system-ui, sans-serif"; g.textAlign = "center"; g.fillText(note, W / 2, H - 16); }
    }
    function poly(pts, fill) { g.beginPath(); pts.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.closePath(); g.fillStyle = fill; g.fill(); }

    /* ---------- tương tác: kéo để xoay, cuộn để phóng to, bấm đúp để về góc mặc định ---------- */
    if (opts.interactive !== false) wire();
    function wire() {
      cv.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY }; cv.setPointerCapture(e.pointerId); cv.style.cursor = "grabbing"; });
      cv.addEventListener("pointermove", (e) => {
        if (!drag) return;
        aim.yaw = Math.max(-Math.PI, Math.min(Math.PI, aim.yaw + (e.clientX - drag.x) * 0.006));
        aim.pitch = Math.max(0.08, Math.min(1.4, aim.pitch + (e.clientY - drag.y) * 0.005));
        drag = { x: e.clientX, y: e.clientY }; kick();
      });
      const end = () => { drag = null; cv.style.cursor = ""; };
      cv.addEventListener("pointerup", end); cv.addEventListener("pointercancel", end);
      cv.addEventListener("wheel", (e) => { e.preventDefault(); aim.dist = Math.max(9, Math.min(80, aim.dist * Math.exp(e.deltaY * 0.001))); kick(); }, { passive: false });
      cv.addEventListener("dblclick", () => { Object.assign(aim, home); kick(); });
    }
    function kick() { if (!raf) { last = 0; raf = requestAnimationFrame(frame); } }
    new IntersectionObserver(([en]) => { visible = en.isIntersecting && !document.hidden; if (visible) kick(); }).observe(cv);
    document.addEventListener("visibilitychange", () => { visible = !document.hidden && cv.offsetParent !== null; if (visible) kick(); });
    new ResizeObserver(() => kick()).observe(cv);
    return {
      view(name) { if (VIEWS[name]) { Object.assign(aim, VIEWS[name]); kick(); } },
      redraw: kick,
    };
  }
  window.RWScene3D = { create };
})();
