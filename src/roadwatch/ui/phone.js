/* Đo trên điện thoại (iPhone, Safari). Hai đường gửi camera sau và GPS tới laptop:
   - "ws" (mặc định): WebSocket /api/phone/ws trên chính kết nối HTTPS của trang: ảnh JPEG từng khung, gửi khung sau
     khi laptop báo đã nhận khung trước (không dồn hàng đợi khi mạng chậm); đi được qua 4G, VPN, proxy;
   - "rtc": WebRTC (POST /api/phone/offer), GPS trên kênh dữ liệu; ít dữ liệu hơn nhưng chỉ nối được khi cùng mạng.
   Laptop đo và quyết định cảnh báo; trang nhận LiveStatus qua /api/ws, hiện số đo
   và phát câu tiếng Việt. Safari chỉ cho camera, vị trí khi trang là HTTPS, và chỉ cho phát âm thanh sau một lần
   chạm: lần chạm "Bắt đầu đo" mở khoá cả ba. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const LEVEL_VI = { info: "Nhắc", warning: "Cảnh báo", emergency: "Khẩn cấp" };
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);
  const nf = (v, d = 1) => isNum(v) ? v.toLocaleString("vi-VN", { minimumFractionDigits: d, maximumFractionDigits: d }) : "—";
  const detail = (b, status) => {
    if (b && typeof b.detail === "string") return b.detail;
    if (b && Array.isArray(b.detail)) return b.detail.map((e) => e.msg).join("; ");   // 422 của FastAPI
    return `Lỗi ${status}`;
  };
  async function call(url, opts) {
    let r;
    try { r = await fetch(url, opts); } catch { throw new Error("Mất kết nối tới laptop"); }
    if (r.status === 401) location.assign("/login?next=/phone");
    let b = null; try { b = await r.json(); } catch { /* không có thân JSON */ }
    if (!r.ok) throw new Error(detail(b, r.status));
    return b;
  }

  let cfg = null;
  call("/api/config").then((c) => { cfg = c; }).catch(() => {});

  /* ---------- trạng thái một lần đo ---------- */
  let S = null;        // tài nguyên của lần đo đang mở: { pc, channel, ws, stream, watchId, wake }
  let runId = null;    // lần đo trên laptop; giữ tới khi laptop báo xong (sau khi bấm Dừng vẫn chờ bản tin cuối)
  let heard;           // khoá câu nói cuối đã xử lý; undefined = chưa nhận bản tin nào của lần đo này
  const voice = new Audio();   // một phần tử dùng lại: Safari chỉ cho phần tử đã phát trong lần chạm

  function show(view) {
    for (const v of ["setup", "run", "end"]) $(`ph-${v}`).hidden = v !== view;
    document.body.classList.toggle("running", view === "run");   // màn đo: camera toàn màn hình
  }
  function conn(text, dot) {
    $("ph-conn").lastElementChild.textContent = text; $("ph-conn").firstElementChild.className = "dot " + (dot || "");
    $("ph-conn-run").textContent = dot === "ok" ? "" : text;   // trên màn đo chỉ hiện khi chưa ổn
  }
  function landscape() { return window.innerWidth > window.innerHeight; }
  function checkRotate() { $("ph-rotate").hidden = landscape() || !S; }
  addEventListener("resize", checkRotate);

  async function unlockAudio() {
    voice.muted = true; voice.src = "/api/phrases/info";
    try { await voice.play(); voice.pause(); } catch { /* chưa có file câu nói: vẫn đo, chỉ không nghe */ }
    voice.muted = false;
  }
  function speak(kind) { voice.src = `/api/phrases/${kind}`; voice.play().catch(() => {}); }

  async function wakeLock() {   // giữ màn hình sáng khi đang đo (iOS 16.4+)
    try { if (S && navigator.wakeLock) S.wake = await navigator.wakeLock.request("screen"); } catch { /* không hỗ trợ */ }
  }
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && S) wakeLock(); });

  async function camera(height = 720) {   // 960: 4:3 khi model chạy trên máy (thêm khoảng nhìn dọc khi điện thoại chúc lên/xuống)
    const want = { width: { ideal: 1280 }, height: { ideal: height }, frameRate: { ideal: 30, max: 30 } };
    try { return await navigator.mediaDevices.getUserMedia({ audio: false, video: { ...want, facingMode: { exact: "environment" } } }); }
    catch (e) {
      if (e.name === "NotAllowedError") throw new Error("Chưa cho phép camera: Cài đặt › Safari › Camera › Cho phép");
      return navigator.mediaDevices.getUserMedia({ audio: false, video: { ...want, facingMode: "environment" } });
    }
  }

  function gatherIce(pc) {
    if (pc.iceGatheringState === "complete") return Promise.resolve();
    return new Promise((resolve) => {
      const done = () => { clearTimeout(timer); pc.removeEventListener("icegatheringstatechange", changed); resolve(); };
      const changed = () => { if (pc.iceGatheringState === "complete") done(); };
      const timer = setTimeout(done, 4000);   // đủ địa chỉ trong mạng hotspot; không chờ STUN quá lâu
      pc.addEventListener("icegatheringstatechange", changed);
    });
  }

  async function start() {
    $("ph-err").textContent = "";
    if (!window.isSecureContext || !navigator.mediaDevices) { $("ph-err").textContent = "Trang cần mở qua HTTPS để dùng camera và vị trí."; return; }
    if ($("ph-via").value === "rtc" && !window.RTCPeerConnection) { $("ph-err").textContent = "Trình duyệt chưa hỗ trợ WebRTC."; return; }
    const d = Number($("ph-d").value), fmm = Number($("ph-fmm").value);
    if (!(d >= 0 && d <= 5)) { $("ph-err").textContent = "Camera tới cản trước phải trong 0–5 m."; return; }
    if (!(fmm > 0 && fmm <= 300)) { $("ph-err").textContent = "Tiêu cự phải trong 0–300 mm."; return; }
    if (!landscape()) { $("ph-err").textContent = "Xoay ngang điện thoại trước khi bắt đầu."; return; }
    $("ph-start").disabled = true; conn("Đang mở camera…", "run");
    S = { pc: null, channel: null, ws: null, stream: null, watchId: null, wake: null };
    runId = null; heard = undefined;
    try {
      await unlockAudio();
      S.stream = await camera($("ph-via").value.startsWith("device") ? 960 : 720);
      $("ph-cam").srcObject = S.stream;
      wakeLock();
      const settings = { d, f_mm: fmm, auto_focal: $("ph-auto").checked };
      if ($("ph-via").value.startsWith("device")) { await startDevice(settings); return; }
      if ($("ph-via").value === "ws") { await startWs(settings); return; }
      const rtc = await call("/api/rtc");
      const pc = S.pc = new RTCPeerConnection(rtc);
      const track = S.stream.getVideoTracks()[0];
      const sender = pc.addTransceiver(track, { direction: "sendonly", streams: [S.stream] }).sender;
      try {   // giữ độ phân giải, giảm khung hình khi mạng yếu: model cần ảnh rõ hơn là nhiều khung
        const p = sender.getParameters(); p.degradationPreference = "maintain-resolution"; await sender.setParameters(p);
      } catch { /* Safari cũ */ }
      S.channel = pc.createDataChannel("gps", { ordered: false, maxRetransmits: 0 });
      S.channel.onmessage = (event) => {
        if (!S || S.pc !== pc) return;
        let msg; try { msg = JSON.parse(event.data); } catch { return; }
        if (Object.hasOwn(msg, "lane")) S.geo = { ...msg, at: performance.now() };
      };
      pc.onconnectionstatechange = () => {
        if (!S || S.pc !== pc) return;
        const st = pc.connectionState;
        if (st === "connected") conn("Đang đo", "ok");
        else if (st === "failed" || st === "disconnected") conn("Mất kết nối video tới laptop", "bad");
      };
      await pc.setLocalDescription(await pc.createOffer());
      conn("Đang nối tới laptop…", "run");
      await gatherIce(pc);
      const ans = await call("/api/phone/offer", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "offer", sdp: pc.localDescription.sdp, ...settings })
      });
      runId = ans.run_id;
      await pc.setRemoteDescription({ type: "answer", sdp: ans.sdp });
      startGps();
      show("run"); checkRotate();
      S.frameW = $("ph-cam").videoWidth;
      requestAnimationFrame(paint);
    } catch (e) {
      teardown();
      show("setup"); conn("Chưa đo");
      $("ph-err").textContent = e && e.message ? e.message : String(e);
    } finally { $("ph-start").disabled = false; }
  }

  /* ---------- đường "ws": ảnh JPEG qua WebSocket ----------
     Gửi theo nhịp 50 ms, nhiều khung chưa được laptop báo nhận cùng lúc: qua 4G + relay một vòng đi về có thể hơn
     1 s, chờ từng khung thì chỉ còn 1–2 khung/s. Số khung gửi trước tự chỉnh theo độ trễ: khung cũ nhất chưa được báo
     nhận lâu hơn vòng đi về thấp nhất cộng QUEUE_MS nghĩa là ảnh đang xếp hàng (mạng không đủ băng thông) thì ngừng
     gửi thêm, nên độ trễ không phình ra; mạng xa mà đủ băng thông thì gửi trước tới MAX_INFLIGHT khung. */
  const FRAME_W = 640, FRAME_Q = .7, FRAME_MS = 50, MAX_INFLIGHT = 12, QUEUE_MS = 250;   // model chạy 20 Hz
  async function startWs(settings) {
    show("run"); checkRotate();
    const cam = $("ph-cam"); await cam.play().catch(() => {});
    const ws = S.ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/phone/ws?${new URLSearchParams(settings)}`);
    conn("Đang nối tới laptop…", "run");
    runId = await new Promise((resolve, reject) => {
      ws.onmessage = (m) => { const b = JSON.parse(m.data); if (b.run_id) resolve(b.run_id); };
      ws.onclose = (e) => reject(new Error(e.code === 1008 ? "Laptop từ chối: đăng nhập lại hoặc kiểm tra thông số" : "Không nối được tới laptop"));
    });
    const canvas = document.createElement("canvas"), ctx = canvas.getContext("2d");
    const sentAt = [];   // performance.now() của các khung đã gửi, chưa được báo nhận (theo thứ tự)
    let encoding = false, sent = 0, acked = 0, rtt = null, minRtt = Infinity, first = true;
    const alive = () => S && S.ws === ws && ws.readyState === WebSocket.OPEN;
    const tick = () => {   // mỗi FRAME_MS: gửi khung mới nếu còn chỗ; lỗi ở một khung không làm dừng nhịp
      if (!alive()) return;
      setTimeout(tick, FRAME_MS);
      if (encoding || sentAt.length >= MAX_INFLIGHT || !cam.videoWidth) return;
      if (sentAt.length && performance.now() - sentAt[0] > (minRtt === Infinity ? 1500 : minRtt + QUEUE_MS)) return;   // đang xếp hàng
      if (ws.bufferedAmount > 256 * 1024) return;   // mạng không kịp đẩy đi: bỏ khung này
      const w = Math.min(FRAME_W, cam.videoWidth) & ~1, h = Math.round(w * cam.videoHeight / cam.videoWidth) & ~1;
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
      S.frameW = w;   // bề rộng ảnh laptop nhận: góc nhìn ngang = 2·atan(w / 2 / fy)
      try { ctx.drawImage(cam, 0, 0, w, h); } catch { return; }
      encoding = true;
      canvas.toBlob((b) => {
        encoding = false;
        if (!b || !alive()) return;
        sentAt.push(performance.now()); sent++; ws.send(b);
      }, "image/jpeg", FRAME_Q);
    };
    ws.onmessage = (m) => {   // {ack: n}: laptop đã nhận khung thứ n; {overlay}: làn và xe dẫn đầu mới nhất
      const b = JSON.parse(m.data);
      if (b.overlay) { S.geo = { ...b.overlay, at: performance.now() }; return; }
      if (!b.ack) return;
      if (first) { first = false; conn("Đang đo", "ok"); }
      const t = sentAt.shift(); acked = b.ack;
      if (t !== undefined) {
        const r = performance.now() - t;
        rtt = rtt === null ? r : .8 * rtt + .2 * r; minRtt = Math.min(minRtt, r);
      }
    };
    ws.onclose = () => { if (S && S.ws === ws) conn("Mất kết nối tới laptop", "bad"); };
    S.link = () => `đi về ${rtt === null ? "—" : Math.round(rtt)} ms (min ${minRtt === Infinity ? "—" : Math.round(minRtt)}) · ${sentAt.length} chờ · ${acked}/${sent}`;
    startGps();
    tick();
    requestAnimationFrame(paint);
  }

  /* ---------- làn và xe dẫn đầu trên camera (như HUD của video đã chú thích: thảm xanh, tam giác vàng/đỏ) ----------
     Toạ độ là tỉ lệ của khung ảnh đã gửi; khung đó là cả hình camera, nên chỉ cần đổi sang vùng hiện của <video>
     (object-fit: contain). Hình vẽ trễ hơn camera đúng bằng thời gian ảnh đi về laptop. */
  const GEO_STALE_MS = 1000;
  function paint() {
    const cv = $("ph-overlay"), cam = $("ph-cam"), ctx = cv.getContext("2d");
    const W = cv.clientWidth, H = cv.clientHeight, dpr = window.devicePixelRatio || 1;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
    if (!S) return;
    requestAnimationFrame(paint);
    const now = performance.now(), g = S.geo;
    if (!g || now - g.at > GEO_STALE_MS || !cam.videoWidth) { S.drawn = null; return; }
    /* Hình từ laptop tới ~10–20 lần/giây, màn hình vẽ 60 lần/giây: tiến dần tới hình mới (~90 ms) thay vì nhảy,
       cùng kiểu làm mượt với HUD trên video (hud.LaneSmoother) */
    const k1 = S.drawn ? 1 - Math.exp(-(now - S.drawn.t) / 90) : 1;
    const mix = (a, b) => a.map(([u, v], i) => [u + (b[i][0] - u) * k1, v + (b[i][1] - v) * k1]);
    const ease = (cur, tgt) => !tgt ? null : !cur || cur.left.length !== tgt.left.length || cur.right.length !== tgt.right.length
      ? { left: tgt.left.map((p) => [...p]), right: tgt.right.map((p) => [...p]) } : { left: mix(cur.left, tgt.left), right: mix(cur.right, tgt.right) };
    const d = S.drawn || {};
    const lead = !g.lead ? null : !d.lead ? { ...g.lead }
      : { ...g.lead, u: d.lead.u + (g.lead.u - d.lead.u) * k1, v: d.lead.v + (g.lead.v - d.lead.v) * k1 };
    S.drawn = { t: now, lane: ease(d.lane, g.lane), path: ease(d.path, g.path), lead };
    const e = S.drawn;
    const a = cam.videoWidth / cam.videoHeight;
    let dw = W, dh = W / a; if (dh > H) { dh = H; dw = H * a; }
    const ox = (W - dw) / 2, oy = (H - dh) / 2, P = ([u, v]) => [ox + u * dw, oy + v * dh], k = dw / 1164;
    const path = (pts) => pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    /* Như HUD trên video (hud.draw_lane): thảm xanh ngọc từ mép dưới ảnh, dải trắng theo hướng đi, viền sáng trên cùng */
    const band = (b, near, far) => {   // tô dải giữa hai đường, gần đậm xa nhạt
      const l = b.left.map(P), r = b.right.map(P);
      const grad = ctx.createLinearGradient(0, l[0][1], 0, l[l.length - 1][1]);
      grad.addColorStop(0, near); grad.addColorStop(1, far);
      ctx.beginPath(); path(l); for (let i = r.length - 1; i >= 0; i--) ctx.lineTo(...r[i]); ctx.closePath();
      ctx.fillStyle = grad; ctx.fill();
      return [l, r];
    };
    const edges = e.lane ? band(e.lane, "rgba(64, 172, 150, .42)", "rgba(64, 172, 150, .22)") : null;
    if (e.path) band(e.path, "rgba(225, 248, 232, .55)", "rgba(225, 248, 232, .2)");   // hướng đi dự đoán
    if (edges) {   // viền mảnh, bo tròn, quầng sáng nhẹ
      ctx.save();
      ctx.lineWidth = Math.max(2, 3 * k); ctx.strokeStyle = "rgb(90, 235, 170)"; ctx.lineJoin = ctx.lineCap = "round";
      ctx.shadowColor = "rgba(90, 235, 170, .6)"; ctx.shadowBlur = Math.max(4, 8 * k);
      for (const line of edges) { ctx.beginPath(); path(line); ctx.stroke(); }
      ctx.restore();
    }
    if (e.lead) {
      const [u, v] = P([e.lead.u, e.lead.v]);
      const sz = Math.min(30, Math.max(15, 25 * 30 / (e.lead.dist_m / 3 + 30))) * 1.4 * k;
      const tri = (top, side, bottom) => { ctx.beginPath(); ctx.moveTo(u, v - sz * top); ctx.lineTo(u + sz * side, v + sz * bottom); ctx.lineTo(u - sz * side, v + sz * bottom); ctx.closePath(); };
      tri(.6, 1.45, .85); ctx.fillStyle = "rgba(40, 40, 40, .45)"; ctx.fill();
      tri(.35, 1.1, .65); ctx.fillStyle = e.lead.close ? "rgb(230, 40, 40)" : "rgb(255, 210, 0)"; ctx.fill();
    }
  }

  /* ---------- đường "device": model chạy ngay trên điện thoại (onphone/engine.mjs), không gửi ảnh ---------- */
  let deviceSession = null, deviceKey = null;   // chỉ giữ một phiên trên iPhone để hạn chế bộ nhớ
  async function startDevice(settings) {
    show("run"); checkRotate();
    const cam = $("ph-cam"); await cam.play().catch(() => {});
    for (let k = 0; k < 50 && !cam.videoWidth; k++) await new Promise((r) => setTimeout(r, 100));
    const { loadModel, DeviceRun, PhoneGps } = await import("/ui/onphone/engine.mjs");
    const { loadPhoneModel } = await import("/ui/onphone/backend.mjs");
    const mode = $("ph-via").value === "device-wasm" || new URLSearchParams(location.search).get("ep") === "wasm" ? "wasm" : "auto";
    let ep = mode === "wasm" ? "wasm" : "webgpu";
    const report = (o) => fetch("/api/bench/result", { method: "POST", headers: { "Content-Type": "application/json" },   // nhật ký về laptop
      body: JSON.stringify({ kind: "device", ep, ua: navigator.userAgent, ...o }) }).catch(() => {});
    const model = new URLSearchParams(location.search).get("model");   // ?model=fp32: thử bản FP32 trên GPU
    const gpuModel = model === "fp32" ? "/ortweb/gr14VinAI.fp32.onnx" : "/ortweb/gr14VinAI.mixed.onnx";
    const loaded = await loadPhoneModel(async (candidate, url) => {
      const key = `${candidate}:${url}`;
      if (deviceSession && deviceKey === key) return deviceSession;
      if (deviceSession) { await deviceSession.release(); deviceSession = null; deviceKey = null; }
      const t = performance.now();
      report({ stage: "load model", ep: candidate });
      const session = await loadModel((text) => conn(text, "run"), candidate, url);
      report({ stage: "model ready", ep: candidate, load_ms: Math.round(performance.now() - t) });
      deviceSession = session; deviceKey = key;
      return session;
    }, mode, (text) => { report({ stage: "gpu fallback", error: text }); conn(text, "run"); }, gpuModel);
    const session = loaded.session; ep = loaded.ep;
    if (!S) return;   // đã bấm Dừng trong lúc tải
    S.gps = new PhoneGps();
    const run = S.device = new DeviceRun({ session, video: cam, dCamBumper: settings.d, fMm: settings.f_mm, gps: S.gps,
      onStatus: (st) => {
        const dev = st.ops && st.ops.device;
        if (dev && S) { S.frameW = dev.size[0]; S.dev = dev; }
        if (st.state === "running" && st.measure && $("ph-conn").lastElementChild.textContent !== "Đang đo") conn("Đang đo", "ok");
        onStatus(st);
      },
      onOverlay: (o) => { if (S) S.geo = { ...o, at: performance.now() }; }, report,
      prep: new URLSearchParams(location.search).get("prep") === "gpu" ? "gpu" : "cpu" });   // ?prep=gpu: nắn ảnh bằng GPU (thử)
    runId = run.runId; heard = undefined;
    S.link = () => S.dev ? `${ep === "wasm" ? "CPU" : "GPU"} · nắn ảnh (${S.dev.prep}) ${S.dev.prep_ms} ms · model ${S.dev.model_ms} ms` : `trên máy · ${ep === "wasm" ? "CPU" : "GPU"}`;
    $("ph-fps-l").textContent = "điện thoại";
    startGps();
    requestAnimationFrame(paint);
    run.start().catch((e) => {
      report({ stage: "error", error: e.message || String(e) });
      if (deviceSession === session) { deviceSession = null; deviceKey = null; }
      session.release().catch((releaseError) => report({ stage: "release error", error: String(releaseError) }));
      if (runId === run.runId) finish({ state: "failed", error: `${e.message || e}${ep === "webgpu" ? ". Có thể thử lại với chế độ CPU." : ""}` });
    });
  }

  function sendFix(fix) {
    if (S.device && S.gps) S.gps.add((performance.now() - S.device.t0) / 1000, fix);
    const msg = JSON.stringify(fix);
    if (S.ws && S.ws.readyState === WebSocket.OPEN) S.ws.send(msg);
    else if (S.channel && S.channel.readyState === "open") S.channel.send(msg);
  }

  /* Tốc độ GPS hiện thẳng từ điện thoại (không chờ laptop đồng bộ GPS); quá GPS_STALE_MS không có tin thì "—" */
  const GPS_STALE_MS = 3000;
  let gpsFix = null;   // { kmh, at }
  function showGps(note) {
    const fresh = gpsFix && performance.now() - gpsFix.at <= GPS_STALE_MS;
    $("ph-v-gps").textContent = fresh && isNum(gpsFix.kmh) ? nf(gpsFix.kmh, 0) : "—";
    if (note !== undefined) $("ph-gps-s").textContent = note;
  }
  setInterval(() => { if (S) { showGps(); $("ph-link").textContent = S.link ? S.link() : "WebRTC"; } }, 1000);

  function startGps() {
    gpsFix = null; showGps("km/h");
    if (!navigator.geolocation) { showGps("không có GPS"); return; }
    S.watchId = navigator.geolocation.watchPosition((p) => {
      if (!S) return;
      const c = p.coords, speed = isNum(c.speed) && c.speed >= 0 ? c.speed : null;
      sendFix({ speed, lat: c.latitude, lon: c.longitude, acc: c.accuracy });
      gpsFix = { kmh: speed === null ? null : speed * 3.6, at: performance.now() };
      showGps(speed === null ? "chưa có tốc độ" : "km/h");
    }, (e) => {
      showGps(e.code === e.PERMISSION_DENIED ? "chưa cho phép vị trí" : "chưa có tín hiệu");
    }, { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 });
  }

  function teardown() {
    if (!S) return;
    const s = S; S = null;
    if (s.watchId !== null && navigator.geolocation) navigator.geolocation.clearWatch(s.watchId);
    if (s.pc) s.pc.close();
    if (s.ws) s.ws.close();
    if (s.device) s.device.stop();
    if (s.stream) for (const t of s.stream.getTracks()) t.stop();
    if (s.wake) s.wake.release().catch(() => {});
    $("ph-fps-l").textContent = "laptop";
    $("ph-cam").srcObject = null;
    paint();   // S đã là null: xoá lớp vẽ
    checkRotate();
  }

  async function stop() {
    if (S && S.device) { S.device.stop(); return; }   // vòng lặp trên máy dừng rồi báo trạng thái "stopped" -> finish
    $("ph-stop").disabled = true;
    conn("Đang lưu phiên…", "run");
    try { await call("/api/stop", { method: "POST" }); } catch { /* laptop tự dừng khi mất video */ }
    teardown();
    $("ph-stop").disabled = false;
    setTimeout(() => { if (runId) finish({ state: "stopped" }); }, 8000);   // không nhận được bản tin cuối
  }

  function finish(st) {
    teardown(); runId = null;
    const said = st.ops && st.ops.said ? Object.entries(st.ops.said).filter(([, n]) => n).map(([k, n]) => `${LEVEL_VI[k] || k}: ${n}`).join(", ") : "";
    $("ph-end-t").textContent = st.state === "failed" ? "Lần đo lỗi" : "Đã dừng đo";
    const where = String(runId || st.run_id || "").startsWith("device-") ? "Đo trên điện thoại (chưa lưu phiên)." : "Phiên đã lưu trên laptop.";
    $("ph-end-s").textContent = st.state === "failed" ? (st.error || "Không rõ lỗi") : `${where}${said ? " Đã nhắc: " + said + "." : " Không có lời nhắc nào."}`;
    show("end"); conn("Chưa đo");
  }

  /* ---------- kết quả từ laptop: WebSocket /api/ws, tự nối lại ---------- */
  function connect() {
    const w = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/ws`);
    w.onmessage = (m) => onStatus(JSON.parse(m.data));
    w.onclose = () => { if (runId) conn("Mất kết nối tới laptop", "bad"); setTimeout(connect, 1000); };
  }
  function onStatus(s) {
    if (!runId || s.run_id !== runId) return;
    if (["done", "stopped", "failed"].includes(s.state)) { finish(s); return; }
    if (!S) return;   // đã bấm Dừng: chỉ chờ bản tin cuối
    const ev = s.events || [], e = ev[ev.length - 1], key = e ? `${e.t_s}/${e.kind}` : null;
    if (key !== heard) { const first = heard === undefined; heard = key; if (e && !first) speak(e.kind); }
    render(s);
  }
  /* Như tab Lái thử: bảng khoảng cách và ô hiệu chuẩn của HUD trên video (hud.draw_panel, hud.draw_debug), khối
     "Đo khoảng cách" (renderLive trong app.js). Thiếu dữ liệu thì "—", không bao giờ 0. */
  const CLOSE_HEADWAY_S = 1;   // hud.CLOSE_HEADWAY_S: khoảng cách thời gian dưới mức này thì số mét và TTC đỏ
  const sg = (v) => isNum(v) ? `${v >= 0 ? "+" : ""}${v.toFixed(2)}` : "—";
  function render(s) {
    const m = s.measure, d = s.decision;
    if (s.state === "loading" || !m) { $("ph-note").textContent = "Đang nạp model…"; return; }
    const lead = m.lead, cal = m.calibration, cs = cal ? cal.status : "";
    const gap = lead ? lead.gap_m : null, std = lead ? lead.gap_std_m : null, thr = d ? d.threshold_m : null, ttc = m.ttc_s;
    const level = d ? d.level : null, egoMps = isNum(m.ego_kmh) ? m.ego_kmh / 3.6 : null;
    const close = isNum(gap) && isNum(egoMps) && egoMps > 1 && gap / egoMps < CLOSE_HEADWAY_S;
    // bảng khoảng cách (hud.draw_panel)
    $("ph-panel").classList.toggle("none", !isNum(gap));
    $("ph-panel").classList.toggle("close", close);
    $("ph-gap").textContent = isNum(gap) ? gap.toFixed(0) : "--";
    $("ph-gap-u").textContent = isNum(gap) ? `m${isNum(std) ? ` ± ${Math.max(std, .5).toFixed(0)}` : ""}` : "Không có xe";
    $("ph-ego").textContent = isNum(m.ego_kmh) ? `${m.ego_kmh.toFixed(0)} km/h` : "";
    $("ph-ttc").textContent = isNum(ttc) ? `TTC ${ttc.toFixed(1)} s` : "";
    const k = /(\d+)\/(\d+)/.exec(cs);
    $("ph-note").textContent = cs.startsWith("calibrating") && k ? `Đang hiệu chỉnh góc camera... ${k[1]}/${k[2]}` : "";
    // ô hiệu chuẩn (hud.draw_debug)
    const w = S && S.frameW, hfov = w && cal && isNum(cal.fy_px) ? 2 * Math.atan(w / 2 / cal.fy_px) * 180 / Math.PI : null;
    $("ph-dbg-angles").textContent = cal ? `pitch ${sg(cal.pitch_deg)} yaw ${sg(cal.yaw_deg)} deg` : "—";
    $("ph-dbg-focal").textContent = cal ? `f ${cal.fy_px}px  hfov ${isNum(hfov) ? hfov.toFixed(0) : "—"} deg  ${cs === "calibrated" ? "CALIBRATED" : cs}` : "";
    $("ph-dbg-gps").textContent = m.ego_source === "gps" ? "GPS điện thoại: đang dùng" : "GPS điện thoại: chưa có tốc độ";
    $("ph-dbg-lead").textContent = `h ${isNum(cal && cal.height_m) ? cal.height_m.toFixed(2) : "—"} m  lead p=${lead && isNum(lead.prob) ? lead.prob.toFixed(2) : "—"}`;
    $("ph-fps").textContent = s.ops && isNum(s.ops.fps) ? `${nf(s.ops.fps, 0)} khung/s` : "—";
    // cảnh báo
    $("ph-alert").dataset.level = level || "";
    $("ph-alert-t").textContent = level ? LEVEL_VI[level] : "Không có cảnh báo";
    $("ph-alert-s").textContent = level ? `“${cfg && cfg.phrases ? cfg.phrases[level] : ""}”` : (d && d.reason) || "RoadWatch đang im lặng";
    // khối "Đo khoảng cách" (renderLive của app.js)
    const below = isNum(gap) && isNum(thr) && gap < thr;
    $("ph-m-gap").textContent = isNum(gap) ? `${nf(gap)} m` : "—";
    $("ph-m-thr").textContent = isNum(thr) ? `${nf(thr, 0)} m` : "—";
    $("ph-m-thr-s").textContent = isNum(thr) ? (isNum(gap) ? (gap < thr ? `hẹp hơn ${nf(thr - gap)} m` : `dư ${nf(gap - thr)} m`) : "") : d ? "dưới 60 km/h: luật không đặt ngưỡng" : "";
    $("ph-m-box").classList.toggle("below", below);
    const scale = Math.max(100, isNum(thr) ? thr * 1.6 : 0, isNum(gap) ? gap * 1.1 : 0);
    $("ph-m-bar").style.width = isNum(gap) ? `${Math.min(100, gap / scale * 100)}%` : "0";
    $("ph-m-bar").classList.toggle("below", below);
    $("ph-m-mark").hidden = !isNum(thr); if (isNum(thr)) $("ph-m-mark").style.left = `${thr / scale * 100}%`;
    // chỉ nhận xe dẫn đầu cùng làn, sau hiệu chuẩn và có trễ chống chập chờn: model có thể thấy xe mà chưa có khoảng cách
    const seen = !!lead && lead.prob >= .5;
    $("ph-m-lead").textContent = !lead ? "—" : isNum(gap) ? "Có" : seen ? "Chưa nhận" : "Không thấy";
    $("ph-m-prob").textContent = !lead ? "tin cậy —" : `tin cậy ${nf(lead.prob, 2)}${isNum(lead.speed_kmh) ? ` · ${nf(lead.speed_kmh, 0)} km/h` : ""}`
      + (!isNum(gap) && seen ? " · chưa đủ điều kiện xe cùng làn" : "");
    $("ph-m-ttc").textContent = isNum(ttc) ? `${nf(ttc)} s` : "—";
    $("ph-m-ttc-box").classList.toggle("hot", isNum(ttc) && !!cfg && ttc <= cfg.ttc_emergency_s);
    $("ph-m-ego").textContent = isNum(m.ego_kmh) ? nf(m.ego_kmh, 0) : "—";
    $("ph-m-ego-s").textContent = m.ego_source === "gps" ? "km/h, theo GPS" : "km/h, ước lượng từ video";
  }

  $("ph-m-toggle").addEventListener("click", () => {
    const min = $("ph-measure").classList.toggle("min");
    $("ph-m-toggle").setAttribute("aria-expanded", String(!min));
  });
  $("ph-start").addEventListener("click", start);
  $("ph-stop").addEventListener("click", stop);
  $("ph-again").addEventListener("click", () => { show("setup"); $("ph-err").textContent = ""; });
  addEventListener("pagehide", () => { if (S) { navigator.sendBeacon && navigator.sendBeacon("/api/stop"); teardown(); } });
  connect();
})();
