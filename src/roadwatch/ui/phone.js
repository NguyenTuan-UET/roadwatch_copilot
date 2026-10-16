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

  // giữ trang và thư viện để mở được khi mất mạng; cần HTTPS và một lần mở khi có mạng (sw.js)
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});

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
  // điện thoại (cảm ứng) phải xoay ngang mới dùng được trang; bản web trên máy tính không bị chặn
  const touch = matchMedia("(pointer: coarse)").matches;
  function checkRotate() { $("ph-rotate").hidden = landscape() || !touch; }
  addEventListener("resize", checkRotate); addEventListener("orientationchange", checkRotate);
  checkRotate();

  /* Mở khoá âm thanh trong lần chạm bằng một đoạn WAV im lặng tạo tại chỗ (blob:), không phụ thuộc file câu nói:
     thiếu /api/phrases/info thì lần phát thử hỏng và Safari không cho phát các câu sau. */
  function silentWav() {
    const n = 800, b = new DataView(new ArrayBuffer(44 + n * 2)), s = (o, t) => [...t].forEach((c, i) => b.setUint8(o + i, c.charCodeAt(0)));
    s(0, "RIFF"); b.setUint32(4, 36 + n * 2, true); s(8, "WAVEfmt "); b.setUint32(16, 16, true); b.setUint16(20, 1, true);
    b.setUint16(22, 1, true); b.setUint32(24, 8000, true); b.setUint32(28, 16000, true); b.setUint16(32, 2, true);
    b.setUint16(34, 16, true); s(36, "data"); b.setUint32(40, n * 2, true);
    return URL.createObjectURL(new Blob([b], { type: "audio/wav" }));
  }
  async function unlockAudio() {
    voice.muted = true; voice.src = silentWav();
    try { await voice.play(); voice.pause(); } catch { /* vẫn đo, chỉ không nghe */ }
    voice.muted = false;
  }
  function speak(kind) { voice.src = `/api/phrases/${kind}`; voice.play().catch(() => {}); }

  async function wakeLock() {   // giữ màn hình sáng khi đang đo (iOS 16.4+)
    try { if (S && navigator.wakeLock) S.wake = await navigator.wakeLock.request("screen"); } catch { /* không hỗ trợ */ }
  }
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && S) wakeLock(); });

  /* 16:9 cho mọi đường (14/10/2026, theo yêu cầu: video rộng như WebRTC). Khung model đủ ảnh khi pitch trong khoảng
     ±8°; chúc xuống quá (−10°: độ phủ 84 %) thì Pipeline báo "unreliable: coverage" và không đo. 4:3 chịu tới khoảng −12°. */
  let clipUrl = null;   // video chọn từ máy (blob:), chỉ đường "Trên điện thoại"
  async function camera(height = 720) {
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
      const file = $("ph-file").files[0];
      if (file && $("ph-via").value.startsWith("device")) {   // video có sẵn thay camera (thử nghiệm, 14/10/2026)
        const cam = $("ph-cam");
        if (clipUrl) URL.revokeObjectURL(clipUrl);
        clipUrl = URL.createObjectURL(file);
        cam.muted = true; cam.loop = false; cam.preload = "auto"; cam.src = clipUrl;
        cam.onended = () => $("ph-stop").click();   // hết video: dừng và lưu như bấm Dừng
        S.clip = file.name;
      } else {
        S.stream = await camera();
        $("ph-cam").srcObject = S.stream;
      }
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
      conn("Đang kết nối server để download…", "run");
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
    conn("Đang kết nối server để download…", "run");
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
     (object-fit: contain: cả khung, kích thước thật; phủ kín màn hình thì phóng khoảng 1,6 lần nên làn rung trông to
     hơn, 14/10/2026). Hình vẽ trễ hơn camera đúng bằng thời gian ảnh đi về laptop. */
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
    let dw = W, dh = W / a; if (dh > H) { dh = H; dw = H * a; }   // contain: cả khung camera, dải đen phần thừa
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
    const cam = $("ph-cam");
    // video quay sẵn: Safari trên iPhone bỏ qua preload, chỉ có kích thước hình sau khi phát; phát rồi dừng ngay, chạy lại
    // từ đầu khi model nạp xong. (lỗi "Chưa có hình camera" khi chỉ đặt preload, 14/10/2026)
    await cam.play().catch((e) => { if (S.clip) conn(`Không phát được video: ${e.message || e}`, "bad"); });
    if (S.clip) cam.pause();
    for (let k = 0; k < 100 && !cam.videoWidth; k++) await new Promise((r) => setTimeout(r, 100));
    const { loadModel, DeviceRun, PhoneGps } = await import("/ui/onphone/engine.mjs");
    const { loadPhoneModel } = await import("/ui/onphone/backend.mjs");
    const mode = $("ph-via").value === "device-wasm" || new URLSearchParams(location.search).get("ep") === "wasm" ? "wasm" : "auto";
    let ep = mode === "wasm" ? "wasm" : "webgpu";
    const report = (o) => fetch("/api/bench/result", { method: "POST", headers: { "Content-Type": "application/json" },   // nhật ký về laptop
      body: JSON.stringify({ kind: "device", ep, ua: navigator.userAgent, ...o }) }).catch(() => {});
    const model = new URLSearchParams(location.search).get("model");   // ?model=fp32: thử bản FP32 trên GPU
    const gpuModel = model === "fp32" ? "/ortweb/gr14VinAI.fp32.onnx" : undefined;   // mặc định: backend.mjs (graph capture)
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
    if (S.clip) {   // chạy từ đầu; mỗi khung ghi lại (đo trên giờ của video) để so với Lái thử
      cam.currentTime = 0; await cam.play().catch((e) => report({ stage: "clip play failed", error: String(e) }));
    }
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
    const clip = S.clip, clipDuration = cam.duration;   // tính trước: dừng xong trang bỏ nguồn video
    run.start().then(() => clip && uploadClip(run, clip, clipDuration, report)).catch((e) => {
      report({ stage: "error", error: e.message || String(e) });
      if (deviceSession === session) { deviceSession = null; deviceKey = null; }
      session.release().catch((releaseError) => report({ stage: "release error", error: String(releaseError) }));
      if (runId === run.runId) finish({ state: "failed", error: `${e.message || e}${ep === "webgpu" ? ". Có thể thử lại với chế độ CPU." : ""}` });
    });
  }

  /* video có sẵn: kết quả từng khung về laptop, để so với cùng video ở Lái thử (compare_phone_clip.py) */
  async function uploadClip(run, name, duration, report) {
    const body = { video: name, duration, started_unix: Date.now() / 1000, ua: navigator.userAgent, size: run.size, fy: run.fy, rows: run.rows };
    try {
      const r = await fetch("/api/phone/clip-result", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const id = (await r.json()).id;
      report({ stage: "clip result sent", id, rows: run.rows.length });
    } catch (e) { report({ stage: "clip result failed", error: String(e) }); }
  }

  function sendFix(fix) {
    if (S.device && S.gps) S.gps.add((performance.now() - S.device.t0) / 1000, fix);
    const msg = JSON.stringify(fix);
    if (S.ws && S.ws.readyState === WebSocket.OPEN) S.ws.send(msg);
    else if (S.channel && S.channel.readyState === "open") S.channel.send(msg);
  }

  /* Tình trạng GPS của điện thoại: hiện ở ô chẩn đoán khi tốc độ đang lấy từ model (vì sao chưa có GPS) */
  let gpsFix = null, gpsNote = "";   // { kmh, at }; "km/h" = đang có tốc độ
  function showGps(note) { if (note !== undefined) gpsNote = note; }
  setInterval(() => { if (S) { showGps(); $("ph-link").textContent = S.link ? S.link() : ""; } }, 1000);

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
    $("ph-cam").onended = null; $("ph-cam").removeAttribute("src"); $("ph-cam").load();
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
    $("ph-end-t").textContent = st.state === "failed" ? "Lần đo lỗi" : "Đã dừng đo";
    $("ph-end-s").textContent = st.state === "failed" ? (st.error || "Không rõ lỗi") : "";   // chỉ báo lỗi khi lỗi; dừng bình thường không hiện gì thêm
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
  /* Như HUD trên video ở Lái thử: một khung khoảng cách và tốc độ (hud.draw_panel, không có dòng radar) và ô hiệu
     chuẩn (hud.draw_debug). Thiếu dữ liệu thì "—", không bao giờ 0. */
  const CLOSE_HEADWAY_S = 1;   // hud.CLOSE_HEADWAY_S: khoảng cách thời gian dưới mức này thì số mét đỏ
  const sg = (v) => isNum(v) ? `${v >= 0 ? "+" : ""}${v.toFixed(2)}` : "—";
  function render(s) {
    const m = s.measure, d = s.decision;
    if (s.state === "loading" || !m) { $("ph-note").textContent = "Đang nạp model…"; return; }
    const lead = m.lead, cal = m.calibration, cs = cal ? cal.status : "";
    const gap = lead ? lead.gap_m : null, std = lead ? lead.gap_std_m : null, level = d ? d.level : null;
    const byGps = m.ego_source === "gps", egoMps = isNum(m.ego_kmh) ? m.ego_kmh / 3.6 : null;
    // khung góc trên trái (hud.draw_panel): khoảng cách, đỏ khi cách xe trước dưới CLOSE_HEADWAY_S giây; tốc độ và nguồn
    $("ph-panel").classList.toggle("none", !isNum(gap));
    $("ph-panel").classList.toggle("close", isNum(gap) && isNum(egoMps) && egoMps > 1 && gap / egoMps < CLOSE_HEADWAY_S);
    $("ph-gap").textContent = isNum(gap) ? gap.toFixed(0) : "--";
    $("ph-gap-u").textContent = isNum(gap) ? `m${isNum(std) ? ` ± ${Math.max(std, .5).toFixed(0)}` : ""}` : "Không có xe";
    $("ph-ego-src").textContent = byGps ? "Tốc độ theo GPS" : "Không có GPS: model ước đoán";
    $("ph-ego").textContent = isNum(m.ego_kmh) ? `${m.ego_kmh.toFixed(0)} km/h` : "—";
    const k = /(\d+)\/(\d+)/.exec(cs);
    $("ph-note").textContent = cs.startsWith("calibrating") && k ? `Đang hiệu chỉnh góc camera... ${k[1]}/${k[2]}` : "";
    // ô hiệu chuẩn (hud.draw_debug)
    const w = S && S.frameW, hfov = w && cal && isNum(cal.fy_px) ? 2 * Math.atan(w / 2 / cal.fy_px) * 180 / Math.PI : null;
    $("ph-dbg-angles").textContent = cal ? `pitch ${sg(cal.pitch_deg)} yaw ${sg(cal.yaw_deg)} deg` : "";
    $("ph-dbg-focal").textContent = cal ? `f ${cal.fy_px}px  hfov ${isNum(hfov) ? hfov.toFixed(0) : "—"} deg  ${cs === "calibrated" ? "CALIBRATED" : cs}` : "";
    $("ph-dbg-gps").textContent = byGps ? "GPS điện thoại: đang dùng"
      : `GPS điện thoại: ${gpsNote && gpsNote !== "km/h" ? gpsNote : "chưa có tốc độ"}`;
    $("ph-dbg-lead").textContent = !cal ? "" : `h ${isNum(cal && cal.height_m) ? cal.height_m.toFixed(2) : "—"} m  lead p=${lead && isNum(lead.prob) ? lead.prob.toFixed(2) : "—"}`;
    const hasFps = s.ops && isNum(s.ops.fps);
    $("ph-fps").textContent = hasFps ? `${nf(s.ops.fps, 0)} khung/s` : "—";
    $("ph-fps").parentElement.hidden = !hasFps;   // chưa có số đo thì không hiện dòng "laptop —" ở góc
    // cảnh báo
    $("ph-alert").dataset.level = level || "";
    $("ph-alert-t").textContent = level ? LEVEL_VI[level] : "Không có cảnh báo";
    $("ph-alert-s").textContent = level ? `“${cfg && cfg.phrases ? cfg.phrases[level] : ""}”` : (d && d.reason) || "RoadWatch đang im lặng";
  }

  /* nút ẩn / hiện ô hiệu chuẩn góc trên phải; nhớ lựa chọn trên máy */
  const FACTS_KEY = "rw-phone-facts";
  function showFacts(on) {
    $("ph-facts").hidden = !on;
    $("ph-facts-sw").checked = on;
    try { localStorage.setItem(FACTS_KEY, on ? "1" : "0"); } catch { /* chế độ riêng tư */ }
  }
  showFacts((() => { try { return localStorage.getItem(FACTS_KEY) !== "0"; } catch { return true; } })());
  $("ph-facts-sw").addEventListener("change", (e) => showFacts(e.target.checked));
  $("ph-gear").addEventListener("click", () => {
    const open = $("ph-settings").hidden;
    $("ph-settings").hidden = !open;
    $("ph-gear").setAttribute("aria-expanded", String(open));
  });
  /* chế độ tập trung lái: video hiển thị đen trắng (CSS filter); khung gửi model vẫn lấy từ video gốc nên giữ màu */
  const FOCUS_KEY = "rw-phone-focus";
  function setFocus(on) {
    $("ph-cam").classList.toggle("focus", on);
    $("ph-focus-sw").checked = on;
    try { localStorage.setItem(FOCUS_KEY, on ? "1" : "0"); } catch { /* chế độ riêng tư */ }
  }
  setFocus((() => { try { return localStorage.getItem(FOCUS_KEY) === "1"; } catch { return false; } })());
  $("ph-focus-sw").addEventListener("change", (e) => setFocus(e.target.checked));
  /* ---------- thiết lập từng bước: quyền riêng tư, điều khoản, camera, gắn máy, khoảng cách và tiêu cự ---------- */
  const CONSENT_KEY = "rw-phone-consent";
  const STEP_SEC = ["Quyền riêng tư", "Điều khoản", "Cài đặt", "Cài đặt", "Cài đặt"];
  const STEP_NOTE = ["Cần mở trang qua HTTPS để Safari cho dùng camera và vị trí", "Bạn có thể xem lại ở bước đầu bất cứ lúc nào",
    "Bước tiếp theo phụ thuộc vào camera bạn chọn", "Gắn chắc điện thoại trước khi bắt đầu đo", ""];
  let step = (() => { try { return localStorage.getItem(CONSENT_KEY) === "1" ? 2 : 0; } catch { return 0; } })();
  function showStep(n) {
    step = n;
    document.querySelectorAll("#ph-setup .wz-step").forEach((el) => { el.hidden = Number(el.dataset.step) !== n; });
    document.querySelectorAll("#wz-dots i").forEach((el, i) => el.classList.toggle("on", i === n));
    $("wz-sec").textContent = STEP_SEC[n]; $("wz-note").textContent = STEP_NOTE[n];
    $("wz-back").hidden = n === 0 || n === 2;
    $("wz-back").textContent = n === 1 ? "Chưa đồng ý" : "Quay lại";
    $("wz-next").hidden = n === 4;
    $("wz-next").textContent = n === 1 ? "Đồng ý và bắt đầu" : "Tiếp tục";
    $("wz-next").disabled = (n === 1 && !$("wz-ack").checked) || (n === 2 && !$("wz-cam-phone").checked);   // camera chưa chọn sẵn
    $("ph-start").hidden = n !== 4;
  }
  $("wz-ack").addEventListener("change", () => showStep(step));
  $("wz-cam-phone").addEventListener("change", (e) => { e.target.closest(".wz-opt").classList.toggle("on", e.target.checked); showStep(step); });
  $("wz-back").addEventListener("click", () => showStep(step === 1 ? 0 : step - 1));
  $("wz-next").addEventListener("click", () => {
    if (step === 1) { try { localStorage.setItem(CONSENT_KEY, "1"); } catch { /* chế độ riêng tư */ } }
    showStep(step + 1);
  });
  // thanh kéo và ô số cùng một giá trị; hình xe dài ra theo khoảng cách ống kính tới cản trước (40 px mỗi mét)
  function dist(v) {
    const d = Number(v), m = Math.min(Math.max(isNum(d) ? d : 0, 0), 3), lx = 140, B = lx + 40 * m;
    const set = (id, o) => { for (const k in o) $(id).setAttribute(k, String(o[k])); };
    $("wz-d-r").value = String(m);
    const ws = Math.min(30, B - lx);
    set("wz-car", { d: `M15 150V122L60 114L${lx - 40} 84H${lx}L${lx + ws} ${84 + ws * 0.9}L${B} 116V150Z` });
    set("wz-w2", { cx: B - 40 }); set("wz-lens", { x: lx - 19 }); set("wz-ld", { cx: lx }); set("wz-lt", { x: lx });
    set("wz-dim", { x1: lx, x2: B }); set("wz-v1", { x1: lx, x2: lx }); set("wz-v2", { x1: B, x2: B });
    set("wz-ar", { d: `M${lx + 7} 22L${lx} 28L${lx + 7} 34M${B - 7} 22L${B} 28L${B - 7} 34` });
    set("wz-dl", { x: (lx + B) / 2 }); $("wz-dl").textContent = `${nf(isNum(d) ? d : 0, 1)} m`;
    set("wz-bl", { x: B + 8 });
  }
  $("wz-d-r").addEventListener("input", () => { $("ph-d").value = $("wz-d-r").value; dist($("ph-d").value); });
  $("ph-d").addEventListener("input", () => dist($("ph-d").value));
  dist($("ph-d").value); showStep(step);

  $("ph-start").addEventListener("click", start);
  $("ph-stop").addEventListener("click", stop);
  $("ph-again").addEventListener("click", () => { show("setup"); $("ph-err").textContent = ""; });
  addEventListener("pagehide", () => { if (S) { navigator.sendBeacon && navigator.sendBeacon("/api/stop"); teardown(); } });
  connect();
})();
