/* Màn buồng lái mở đầu (lấy từ presentation/web-demo/index.html): ảnh buồng lái vẽ lại trên canvas, vô lăng và xe phía trước
   được tách khỏi ảnh để chuyển động. Chạm chữ V: phóng to vào màn hình trung tâm, logo hiện lên, rồi vào web app ở /app. */
(function () {
  "use strict";
  // Chạm V xong thì vào web app (không nhúng iframe: server gửi X-Frame-Options DENY).
  const ENTER_URL = "/app#intro";
  const PHOTO = "/ui/cockpit.png";                 // ảnh buồng lái không có vô lăng (1672×941, vẽ co về 1673×940), cùng nguồn: đọc pixel được
  const WHEEL = "/ui/handle_cut.png";             // vô lăng đã tách nền (handle.png), xoay độc lập nên không còn cắt từ ảnh buồng lái
  const W = 1673, H = 940;
  const $ = (id) => document.getElementById(id);
  const REDUCED = false;                             // bản demo: luôn chạy hoạt cảnh, kể cả khi máy bật "giảm chuyển động"
  const cv = $("cv"), ctx = cv.getContext("2d");

  // pixel geometry measured on the photo
  const RIM = { cx: 358, cy: 530, rx: 238, ry: 228 };            // steering wheel: pivot = hub centre; rx, ry = half width and (foreshortened) half height of the rim
  const WHEEL_PX = { w: 1174, h: 1121, hx: 583, hy: 600 };      // handle_cut.png: size and hub centre in its own pixels
  const LOGO = { cx: 358, cy: 528 };
  const SCREEN = { cx: 835, cy: 445, w: 410, h: 200, view: [645, 385, 320, 140] };
  const ALERT = { x: 818, y: 470 };
  const ROAD_Y = 318;                                             // windshield bottom: the car ahead stays above it
  // lane dashes in perspective: a ground point Z metres ahead sits at y = VP.y + LANE_K / Z; each line runs x = VP.x + slope * (y - VP.y)
  const VP = { x: 795, y: 198 }, LANE_K = 3430, DASH = 3, PERIOD = 12, CRUISE = 68 / 3.6;
  const LANES = [{ slope: -2.72, w: 0.08 }, { slope: -1.09, w: 0.05 }, { slope: 1.08, w: 0.05 }];   // w: dash width per px below the horizon

  let clean, plate, wheel, leadSprite;
  const CAR = [[773, 201], [829, 201], [836, 212], [844, 220], [842, 240], [841, 266], [835, 273], [761, 273], [755, 266], [755, 240], [753, 220], [764, 212]];
  function liftCar(px) {
    // the car ahead, cut along its silhouette; the asphalt behind it is filled by diffusion from the edge
    const x0 = 744, y0 = 193, w = 110, h = 88, d = px.data, at = (x, y) => (y * W + x) * 4;
    const m = document.createElement("canvas"); m.width = w; m.height = h;
    const mx = m.getContext("2d"), poly = (c) => { c.beginPath(); CAR.forEach(([x, y], i) => (i ? c.lineTo(x - x0, y - y0) : c.moveTo(x - x0, y - y0))); c.closePath(); };
    mx.fillStyle = "#fff"; poly(mx); mx.fill(); mx.lineWidth = 7; mx.strokeStyle = "#fff"; mx.stroke();
    const hole = mx.getImageData(0, 0, w, h).data;
    mx.clearRect(0, 0, w, h); mx.filter = "blur(1.2px)"; poly(mx); mx.fill(); mx.filter = "none";
    const soft = mx.getImageData(0, 0, w, h).data;
    const sp = document.createElement("canvas"); sp.width = w; sp.height = h;
    const sx = sp.getContext("2d"), out = sx.createImageData(w, h);
    const fillIdx = [];
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const o = (y * w + x) * 4, i = at(x0 + x, y0 + y);
      out.data[o] = d[i]; out.data[o + 1] = d[i + 1]; out.data[o + 2] = d[i + 2]; out.data[o + 3] = soft[o + 3];
      if (hole[o + 3] > 10 && y0 + y < ROAD_Y) fillIdx.push(x0 + x, y0 + y);
    }
    sx.putImageData(out, 0, 0);
    const n = fillIdx.length / 2, inHole = new Uint8Array(W * H);
    for (let k = 0; k < n; k++) inHole[fillIdx[2 * k + 1] * W + fillIdx[2 * k]] = 1;
    const rows = new Map(); // per row: hole span, filled by a left-to-right blend of the asphalt either side
    for (let k = 0; k < n; k++) { const x = fillIdx[2 * k], y = fillIdx[2 * k + 1], r = rows.get(y) || [x, x]; rows.set(y, [Math.min(r[0], x), Math.max(r[1], x)]); }
    const reddish = (i) => d[i] > d[i + 1] + 28;
    for (const [y, [xl, xr]] of rows) {
      const L = at(xl - 2, y); let R = at(xr + 2, y); if (reddish(R)) R = L;
      for (let x = xl; x <= xr; x++) { if (!inHole[y * W + x]) continue; const f = (x - xl + 1) / (xr - xl + 2), i = at(x, y); for (let c = 0; c < 3; c++) d[i + c] = d[L + c] * (1 - f) + d[R + c] * f; }
    }
    for (let it = 0; it < 120; it++) for (let k = 0; k < n; k++) {
      const x = fillIdx[2 * k], y = fillIdx[2 * k + 1], i = at(x, y);
      for (let c = 0; c < 3; c++) d[i + c] = (d[at(x - 1, y) + c] + d[at(x + 1, y) + c] + d[at(x, y - 1) + c] + d[at(x, Math.min(y + 1, ROAD_Y - 1)) + c]) / 4;
    }
    for (let k = 0; k < n; k++) { const i = at(fillIdx[2 * k], fillIdx[2 * k + 1]), g = (Math.random() - 0.5) * 3; for (let c = 0; c < 3; c++) d[i + c] += g; }
    sp.ox = x0; sp.oy = y0; return sp;
  }
  function eraseLanes(px) {
    // the photo's painted dashes stand still, so they go: each row of each line is blended from the asphalt either side
    const d = px.data, at = (x, y) => (y * W + x) * 4;
    for (const { slope, w } of LANES) for (let y = 225; y < ROAD_Y + 12; y++) {
      const dy = y - VP.y, xc = VP.x + slope * dy, hw = Math.ceil(w * dy * 1.1 + 5);
      const xl = Math.round(xc - hw), xr = Math.round(xc + hw), L = at(xl - 2, y), R = at(xr + 2, y);
      for (let x = xl; x <= xr; x++) { const f = (x - xl + 1) / (xr - xl + 2), i = at(x, y); for (let c = 0; c < 3; c++) d[i + c] = d[L + c] * (1 - f) + d[R + c] * f; }
    }
  }
  function drawLanes(dist) {
    // dashes stream toward the driver at cruising speed; they fade into the haze far ahead
    const off = dist % PERIOD, yAt = (z) => VP.y + LANE_K / z;
    ctx.save(); ctx.beginPath(); ctx.rect(0, VP.y, W, ROAD_Y - VP.y + 12); ctx.clip();
    for (let z = PERIOD - off + 20; z < 220; z += PERIOD) {
      const y1 = yAt(z), y0 = yAt(z + DASH), d1 = y1 - VP.y, d0 = y0 - VP.y;
      ctx.fillStyle = `rgba(236,238,236,${Math.min(0.9, d0 / 45)})`;
      for (const { slope, w } of LANES) {
        const x0 = VP.x + slope * d0, x1 = VP.x + slope * d1, h0 = (w * d0) / 2, h1 = (w * d1) / 2;
        ctx.beginPath(); ctx.moveTo(x0 - h0, y0); ctx.lineTo(x0 + h0, y0); ctx.lineTo(x1 + h1, y1); ctx.lineTo(x1 - h1, y1); ctx.closePath(); ctx.fill();
      }
    }
    ctx.restore();
  }
  async function init() {
    const img = new Image(), wimg = new Image(); img.src = PHOTO; wimg.src = WHEEL; await Promise.all([img.decode(), wimg.decode()]);
    const base = document.createElement("canvas"); base.width = W; base.height = H;
    const bx = base.getContext("2d"); bx.drawImage(img, 0, 0, W, H);
    const px = bx.getImageData(0, 0, W, H);
    leadSprite = liftCar(px);     // the car ahead becomes a movable sprite
    eraseLanes(px);               // painted dashes are redrawn moving, every frame
    bx.putImageData(px, 0, 0);
    clean = base;
    // wheel = the cut-out wheel image (emblem removed; RoadWatch V is drawn on the hub), foreshortened like the rim ellipse
    const k = (RIM.rx * 2) / WHEEL_PX.w, kv = k * RIM.ry / RIM.rx;
    wheel = document.createElement("canvas"); wheel.width = W; wheel.height = H;
    wheel.getContext("2d").drawImage(wimg, RIM.cx - WHEEL_PX.hx * k, RIM.cy - WHEEL_PX.hy * kv, WHEEL_PX.w * k, WHEEL_PX.h * kv);
    // plate = the cabin photo; it has no wheel, so a turned spoke uncovers the real dashboard
    plate = clean;
    $("loading").hidden = true; requestAnimationFrame(frame);
  }

  let t = 0, last = null, started = false, flash = 0, angle = 0, slide = 0, calm = 0, travelled = 0;
  // steering as a damped spring: the wheel overshoots a little and settles, like hands correcting
  const SPRING = { k: 34, c: 8.5 };
  let target = 0, steer = 0, vel = 0;
  function frame(now) {
    const dt = last === null ? 0 : Math.min(0.05, (now - last) / 1000); last = now;
    if (!REDUCED) t += dt;
    flash = Math.max(0, flash - dt * 0.8);
    if (!REDUCED) for (let k = 0; k < 4; k++) { const h = dt / 4; vel += (SPRING.k * (target - steer) - SPRING.c * vel) * h; steer += vel * h; }
    else steer = target;
    const sway = REDUCED || started ? 0 : 0.014 * Math.sin(t * 0.73) + 0.007 * Math.sin(t * 1.9 + 1); // small corrections while cruising
    angle = steer + sway;
    engine.update();
    ctx.drawImage(plate, 0, 0);
    if (!REDUCED) travelled += CRUISE * dt;
    drawLanes(travelled);

    // the car ahead: drifts gently, then speeds straight off down the road toward the vanishing point (792, 196)
    const e = slide * slide * slide, bob = REDUCED ? 0 : Math.sin(t * 1.3) * 1.2;
    const s = 1 / (1 + 14 * e), lw = leadSprite.width * s, lh = leadSprite.height * s;
    const bx = 792 + (798 - 792) * s, by = 196 + (272 - 196) * s + bob * (1 - e);   // rear bumper centre on the road
    const lx = bx - 54 * s, ly = by - 79 * s;
    ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W, ROAD_Y); ctx.clip(); ctx.globalAlpha = e > 0.85 ? (1 - e) / 0.15 : 1;
    ctx.drawImage(leadSprite, lx, ly, lw, lh); ctx.restore();

    // collision alert on the center screen breathes; it calms down once the car has slid away
    const [vx, vy, vw, vh] = SCREEN.view, pulse = REDUCED ? 0.5 : 0.5 + 0.5 * Math.sin(t * 6.2), k = 1 - calm;
    if (k > 0) {
      ctx.save(); ctx.beginPath(); ctx.rect(vx, vy, vw, vh); ctx.clip(); ctx.globalCompositeOperation = "lighter";
      const rg = ctx.createRadialGradient(ALERT.x, ALERT.y - 20, 10, ALERT.x, ALERT.y - 20, 190);
      rg.addColorStop(0, `rgba(255,40,30,${0.32 * pulse * k})`); rg.addColorStop(1, "rgba(255,40,30,0)");
      ctx.fillStyle = rg; ctx.fillRect(vx, vy, vw, vh);
      ctx.strokeStyle = `rgba(255,70,60,${0.55 * pulse * k})`; ctx.lineWidth = 2; ctx.strokeRect(vx + 2, vy + 2, vw - 4, vh - 4);
      ctx.restore();
    }
    if (calm > 0) { // view settles to normal: cool the red down
      ctx.save(); ctx.beginPath(); ctx.rect(vx, vy, vw, vh); ctx.clip();
      ctx.globalCompositeOperation = "color"; ctx.globalAlpha = 0.85 * calm; ctx.fillStyle = "#2c6f7c"; ctx.fillRect(vx, vy, vw, vh); ctx.restore();
    }

    // ambient light
    const amb = (REDUCED ? 0.2 : 0.12 + 0.1 * Math.sin(t * 1.4)) + flash;
    ctx.save(); ctx.globalCompositeOperation = "lighter"; ctx.lineCap = "round"; ctx.shadowColor = "#8b5cf6"; ctx.shadowBlur = 14;
    ctx.strokeStyle = `rgba(139,92,246,${Math.min(1, amb)})`; ctx.lineWidth = 5;
    ctx.beginPath(); ctx.moveTo(1040, 588); ctx.quadraticCurveTo(1300, 584, 1550, 572); ctx.stroke(); // along the chrome trim
    ctx.restore();

    // steering wheel: turns in its own (foreshortened) plane, with the RoadWatch V on the hub
    const turnTo = (a) => { ctx.translate(RIM.cx, RIM.cy); ctx.scale(1, RIM.ry / RIM.rx); ctx.rotate(a); ctx.scale(1, RIM.rx / RIM.ry); ctx.translate(-RIM.cx, -RIM.cy); };
    if (Math.abs(vel) > 0.35) { // motion blur while the wheel spins quickly
      for (const [lag, alpha] of [[0.05, 0.22], [0.025, 0.3]]) { ctx.save(); ctx.globalAlpha = alpha; turnTo(angle - vel * lag); ctx.drawImage(wheel, 0, 0); ctx.restore(); }
    }
    ctx.save(); turnTo(angle); ctx.drawImage(wheel, 0, 0);
    drawV(started ? 1 : 0.5 + 0.5 * Math.sin(t * 2.6));
    ctx.restore();
    if (blinker > 0 && Math.floor(t * 3) % 2 === 0) { // right turn signal lamp on the cluster
      ctx.save(); ctx.fillStyle = "#3fe08a"; ctx.shadowColor = "#3fe08a"; ctx.shadowBlur = 12;
      ctx.beginPath(); ctx.moveTo(530, 445); ctx.lineTo(516, 435); ctx.lineTo(516, 441); ctx.lineTo(504, 441); ctx.lineTo(504, 449); ctx.lineTo(516, 449); ctx.lineTo(516, 455); ctx.closePath(); ctx.fill(); ctx.restore();
    }
    if (!started && !REDUCED) { // invitation ring around the hub: a steady glowing ring plus two pulses spreading outward, so the V reads as the thing to touch
      const p = (t * 0.55) % 1, E = (r) => ctx.ellipse(LOGO.cx, LOGO.cy, 72 * r, 66 * r, 0, 0, Math.PI * 2);
      ctx.save(); ctx.shadowColor = "#46d6e6"; ctx.shadowBlur = 18 + 10 * Math.sin(t * 3.2);
      ctx.strokeStyle = "rgba(90,235,250,.95)"; ctx.lineWidth = 5; ctx.beginPath(); E(1); ctx.stroke();
      ctx.shadowBlur = 0; ctx.fillStyle = "rgba(70,214,230,.10)"; ctx.fill();
      for (const q of [p, (p + 0.5) % 1]) { ctx.strokeStyle = `rgba(110,240,255,${0.85 * (1 - q)})`; ctx.lineWidth = 4 * (1 - q) + 1; ctx.beginPath(); E(1 + q * 0.7); ctx.stroke(); }
      ctx.restore();
    }
    requestAnimationFrame(frame);
  }
  function drawV(glow) {
    const { cx, cy } = LOGO;
    const g = ctx.createLinearGradient(cx - 40, cy - 40, cx + 40, cy + 40);
    g.addColorStop(0, "#f6f8fa"); g.addColorStop(0.45, "#9aa3ad"); g.addColorStop(0.55, "#d9dfe5"); g.addColorStop(1, "#7d868f");
    ctx.save(); ctx.shadowColor = "rgba(0,0,0,.7)"; ctx.shadowBlur = 6; ctx.shadowOffsetY = 2;
    ctx.strokeStyle = g; ctx.lineWidth = 11; ctx.lineJoin = "round"; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(cx - 34, cy - 32); ctx.lineTo(cx, cy + 34); ctx.lineTo(cx + 34, cy - 32); ctx.stroke();
    ctx.shadowColor = "#46d6e6"; ctx.shadowBlur = 6 + 12 * glow; ctx.shadowOffsetY = 0;
    ctx.strokeStyle = `rgba(70,214,230,${0.55 + 0.45 * glow})`; ctx.lineWidth = 3.5;
    ctx.beginPath(); ctx.moveTo(cx - 14, cy - 32); ctx.lineTo(cx, cy - 4); ctx.lineTo(cx + 14, cy - 32); ctx.stroke();
    ctx.restore();
  }

  /* engine sound, synthesised: firing pulses of a 4-cylinder engine, intake noise, road and wind */
  let actx = null, blinker = 0;
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
        b.drawImage(clean, innerWidth / 2 - SCREEN.cx * k, innerHeight / 2 - SCREEN.cy * k, W * k, H * k);
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
