/* RoadWatch Copilot web app: một trang, điều hướng bằng #hash, chỉ gọi API cùng nguồn của src/roadwatch/web.py.
   Hợp đồng: src/roadwatch/schemas.py (LiveStatus, RunInfo, BtBConfig, ...). decisions.json: src/roadwatch/job.py.
   Quy ước: giá trị thiếu (null) hiện "—", không bao giờ hiện 0; thời gian là giây của video (t_s), không phải giờ máy. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const LEVELS = ["info", "warning", "emergency"];
  const LEVEL_VI = { info: "Nhắc", warning: "Cảnh báo", emergency: "Khẩn cấp" };
  const STATE_VI = { idle: "Chờ video", loading: "Đang nạp", running: "Đang chạy", done: "Xong", stopped: "Đã dừng", failed: "Lỗi" };
  const ST_ICON = { done: "i-check", failed: "i-x", stopped: "i-stop", running: "i-play", loading: "i-play" };
  const HZ = 20;   // BT-A chạy 20 khung/giây (MODEL_HZ): t_s của mọi bản ghi theo nhịp này
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);
  const nf = (v, d = 1) => isNum(v) ? v.toLocaleString("vi-VN", { minimumFractionDigits: d, maximumFractionDigits: d }) : "—";
  const ni = (v) => isNum(v) ? v.toLocaleString("vi-VN") : "—";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtT = (t) => { if (!isNum(t)) return "—"; const s = Math.max(0, t), m = Math.floor(s / 60); return `${m}:${(s % 60).toFixed(1).padStart(4, "0")}`; };
  const when = (u) => isNum(u) ? new Date(u * 1000).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" }) : "—";
  const COLOR = {};
  const readColors = () => { const s = getComputedStyle(document.documentElement);
    for (const k of ["accent", "info", "warning", "emergency", "ok", "muted", "line", "fg", "panel", "font-data"]) COLOR[k] = s.getPropertyValue(`--${k}`).trim(); };
  const rgba = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };
  const stateCell = (s) => { const st = s || "running"; return `<span class="st ${st}"><i><svg><use href="#${ST_ICON[st] || "i-play"}"/></svg></i>${STATE_VI[st] || st}</span>`; };

  /* ---------- API ---------- */
  const detail = (b, status) => {
    if (b && typeof b.detail === "string") return b.detail;
    if (b && Array.isArray(b.detail)) return b.detail.map((e) => `${(e.loc || []).slice(-1)[0]}: ${e.msg}`).join("; ");   // 422 của FastAPI
    return `Lỗi ${status}`;
  };
  async function call(url, opts) {
    let r;
    try { r = await fetch(url, opts); } catch { throw new Error("Mất kết nối tới server"); }
    if (r.status === 401) location.assign(`/login?next=${encodeURIComponent('/app' + location.hash)}`);
    let b = null; try { b = await r.json(); } catch { /* không có thân JSON */ }
    if (!r.ok) throw new Error(detail(b, r.status));
    return b;
  }
  call("/api/auth/me").then((account) => {
    $("account-name").textContent = account.username;
    $("account-role").textContent = account.role === "engineer" ? "Kỹ sư" : "Tài xế";
    $("account").hidden = false;
    if (account.role !== "engineer") {
      document.querySelector('[data-route="lab"]').hidden = true;
      if (location.hash === "#lab") location.hash = "#upload";
    }
  }).catch(() => {});
  const setMenu = (open) => { $("account-menu").hidden = !open; $("account-btn").setAttribute("aria-expanded", String(open)); };
  $("account-btn").addEventListener("click", (e) => { e.stopPropagation(); setMenu($("account-menu").hidden); });
  document.addEventListener("click", (e) => { if (!$("account").contains(e.target)) setMenu(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setMenu(false); });
  $("logout").addEventListener("click", async () => {
    $("logout").disabled = true;
    try { await call("/api/auth/logout", { method: "POST" }); location.assign("/login"); }
    catch (exc) { $("logout").disabled = false; alert(exc.message); }
  });
  const api = {
    config: () => call("/api/config"),
    runs: () => call("/api/runs"),
    samples: () => call("/api/samples"),
    history: () => call("/api/history"),
    runSample: (id, rt) => call(`/api/samples/${encodeURIComponent(id)}/run?rt=${rt}`, { method: "POST" }),
    stop: () => call("/api/stop", { method: "POST" }),
    del: (id) => call(`/api/runs/${id}`, { method: "DELETE" }),
    file: (id, name) => call(`/api/runs/${id}/files/${name}`),
    text: async (url) => { const r = await fetch(url); if (!r.ok) throw new Error(`Lỗi ${r.status}`); return r.text(); },
    labSegments: () => call("/api/lab/segments"),
    labStatus: () => call("/api/lab/status"),
    labLive: (since) => call(`/api/lab/live?since=${since}`),
    labResult: (id) => call(`/api/lab/segments/${encodeURIComponent(id)}/result`),
    labRun: (id, q) => call(`/api/lab/segments/${encodeURIComponent(id)}/run?${new URLSearchParams(q)}`, { method: "POST" }),
    labStop: () => call("/api/lab/stop", { method: "POST" }),
    uploadRadar: (file) => call(`/api/radar?name=${encodeURIComponent(file.name)}`,
      { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file }),
    uploadGps: (file) => call(`/api/gps?name=${encodeURIComponent(file.name)}`,
      { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file }),
    upload(file, q, onProgress) {   // XHR thay fetch để có tiến độ tải lên; thân request là bytes của video, không multipart
      return new Promise((resolve, reject) => {
        const x = new XMLHttpRequest();
        x.open("POST", `/api/runs?${new URLSearchParams(q)}`);
        x.setRequestHeader("Content-Type", "application/octet-stream");
        const t0 = performance.now();   // tốc độ thật của đường truyền: qua tunnel có thể chậm hơn nhiều so với mạng nội bộ
        x.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total, e.loaded / Math.max((performance.now() - t0) / 1000, 0.1), e.total - e.loaded); };
        x.onload = () => { let b = null; try { b = JSON.parse(x.responseText); } catch { /* không có thân JSON */ }
          x.status >= 200 && x.status < 300 ? resolve(b) : reject(new Error(detail(b, x.status))); };
        x.onerror = () => reject(new Error("Mất kết nối tới server"));
        x.send(file);
      });
    },
  };

  /* ---------- cấu hình BT-B (chỉ đọc) ---------- */
  let cfg = null;
  const cfgReady = api.config().then((c) => { cfg = c; }).catch(() => { cfg = null; });

  /* ---------- trạng thái server ---------- */
  async function health() {
    const el = $("health"), dot = el.querySelector(".dot"), txt = el.lastElementChild;
    try {
      const r = await fetch("/health"), h = await r.json();   // 503 vẫn có thân Health
      dot.className = "dot " + (h.status === "ok" ? "ok" : "warn");
      txt.textContent = !h.model ? "Thiếu model" : h.hung ? "Job bị treo" : "Server sẵn sàng";
    } catch { dot.className = "dot bad"; txt.textContent = "Mất kết nối server"; }
    const ok = dot.classList.contains("ok");   // bình thường chỉ hiện chấm; có sự cố mới mở rộng chữ
    el.classList.toggle("compact", ok);
    el.title = ok ? txt.textContent : "GET /health, kiểm 5 giây một lần";
  }

  /* ---------- âm thanh: kênh chính (docs/specs/roadwatch-api.md, mục 6), bật mặc định. Trình duyệt chỉ cho phát
     sau khi người xem đã bấm vào trang; bị chặn thì nhắc ngay trên nút. ---------- */
  let sound = true, phrasesMissing = false;
  function speak(kind, onMissing) {
    const a = new Audio(`/api/phrases/${kind}`);
    a.addEventListener("error", () => { phrasesMissing = true; onMissing && onMissing(); }, { once: true });
    a.play().catch((err) => { if (err.name === "NotAllowedError") $("sound").title = "Âm thanh: bấm vào trang để nghe"; });
  }

  /* =========================================================================
     Điều hướng
     ========================================================================= */
  const ROUTES = ["intro", "upload", "live", "runs", "lab"];
  let route = "intro";
  const RUN_ID = /^[0-9a-f]{12}$/;
  function go() {   // #trang, hoặc #runs/<run_id> để mở sẵn một lần chạy (chép link được)
    const [h, arg] = location.hash.slice(1).split("/"), r = ROUTES.includes(h) ? h : "intro", id = RUN_ID.test(arg || "") ? arg : null;
    const prev = route; route = r;
    document.querySelectorAll("[data-view]").forEach((el) => { el.hidden = el.dataset.view !== r; });
    document.querySelectorAll("[data-route]").forEach((a) => { if (a.dataset.route === r) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    document.body.classList.toggle("on-intro", r === "intro");
    if (prev === "live" && r !== "live") detachStream();
    if (r === "upload") { renderRecent(); }
    if (r === "live") { renderLive(); }
    if (r === "runs") { if (id) wantOpen = id; renderRuns(); }
    if (r === "lab") renderLab(arg);
    if (prev !== r) scrollTo(0, 0);
  }

  /* =========================================================================
     Biểu đồ: trên là khoảng cách và ngưỡng (m), dưới là TTC (s, cắt ở 10 s); nền tô theo mức cảnh báo đang bật.
     pts: [{t, gap, thr, ttc, level}], các giá trị có thể null (đứt nét, không nối qua chỗ trống).
     ========================================================================= */
  function drawChart(cv, pts, o) {
    const dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
    if (!W || !H) return;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    const L = 44, R = 10, T = 8, B = 20, mid = T + (H - T - B) * 0.64, gb = mid - 8, tt = mid + 14, bot = H - B;
    const { t0, t1 } = o, span = Math.max(1e-6, t1 - t0);
    const X = (t) => L + (t - t0) / span * (W - L - R);
    let gmax = 60;
    for (const p of pts) { if (isNum(p.gap)) gmax = Math.max(gmax, p.gap); if (isNum(p.thr)) gmax = Math.max(gmax, p.thr); }
    const gstep = gmax > 150 ? 50 : 20; gmax = Math.ceil(gmax * 1.08 / gstep) * gstep;
    const Yg = (v) => gb - v / gmax * (gb - T), TMAX = 10, Yt = (v) => bot - Math.min(v, TMAX) / TMAX * (bot - tt);
    g.font = `11px ${COLOR["font-data"]}`; g.textBaseline = "middle";
    // nền theo mức
    if (o.levels) {
      let s = 0;
      for (let i = 1; i <= pts.length; i++) {
        if (i < pts.length && pts[i].level === pts[s].level) continue;
        const lv = pts[s].level;
        if (lv) { g.fillStyle = rgba(COLOR[lv], 0.13); const xa = X(pts[s].t), xb = X(i < pts.length ? pts[i].t : pts[i - 1].t + 1 / HZ); g.fillRect(xa, T, Math.max(1, xb - xa), bot - T); }
        s = i;
      }
    }
    // lưới
    g.strokeStyle = COLOR.line; g.fillStyle = COLOR.muted; g.lineWidth = 1;
    for (let v = 0; v <= gmax; v += gstep) { g.beginPath(); g.moveTo(L, Yg(v)); g.lineTo(W - R, Yg(v)); g.stroke(); g.fillText(`${v} m`, 4, Yg(v)); }
    for (const v of [0, 5, 10]) { g.beginPath(); g.moveTo(L, Yt(v)); g.lineTo(W - R, Yt(v)); g.stroke(); g.fillText(`${v} s`, 4, Yt(v)); }
    const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200], st = steps.find((x) => span / x <= 8) || 1800;
    g.textAlign = "center";
    for (let v = Math.ceil(t0 / st) * st; v <= t1; v += st) g.fillText(span > 90 ? fmtT(v).replace(/\.\d$/, "") : `${v} s`, X(v), H - 8);
    g.textAlign = "left";
    if (cfg && isNum(cfg.ttc_emergency_s)) {   // ngưỡng TTC khẩn cấp
      g.strokeStyle = rgba(COLOR.emergency, 0.6); g.setLineDash([3, 3]); g.beginPath(); g.moveTo(L, Yt(cfg.ttc_emergency_s)); g.lineTo(W - R, Yt(cfg.ttc_emergency_s)); g.stroke(); g.setLineDash([]);
    }
    const line = (get, Y, col, dash, w = 2) => {
      g.strokeStyle = col; g.lineWidth = w; g.setLineDash(dash); g.beginPath();
      let on = false, pt = null;
      for (const p of pts) {
        const v = get(p);
        if (!isNum(v) || (pt !== null && p.t - pt > 0.3)) on = false;   // không nối qua chỗ thiếu dữ liệu
        if (isNum(v)) { on ? g.lineTo(X(p.t), Y(v)) : g.moveTo(X(p.t), Y(v)); on = true; }
        pt = p.t;
      }
      g.stroke(); g.setLineDash([]);
    };
    if (o.thr) line((p) => p.thr, Yg, COLOR.warning, [6, 4]);
    line((p) => p.gap, Yg, COLOR.accent, []);
    line((p) => isNum(p.ttc) ? Math.min(p.ttc, TMAX) : null, Yt, COLOR.emergency, [], 1.6);
    for (const e of o.events || []) {   // vạch các lần đã nói
      if (e.t_s < t0 || e.t_s > t1) continue;
      g.fillStyle = COLOR[e.kind] || COLOR.fg; g.fillRect(X(e.t_s) - 1.5, T, 3, 10);
    }
    if (isNum(o.head)) { g.fillStyle = COLOR.fg; g.fillRect(X(o.head) - 1, T, 2, bot - T); }
    cv._geo = { t0, t1, L, R, W };
  }
  const chartT = (cv, clientX) => { const r = cv.getBoundingClientRect(), G = cv._geo; if (!G) return null;
    return G.t0 + Math.min(1, Math.max(0, (clientX - r.left - G.L) / (G.W - G.L - G.R))) * (G.t1 - G.t0); };
  const bisect = (frames, t) => { let lo = 0, hi = frames.length - 1; if (hi < 0) return -1;
    while (lo < hi) { const m = (lo + hi) >> 1; frames[m].t_s < t ? lo = m + 1 : hi = m; }
    return lo > 0 && t - frames[lo - 1].t_s < frames[lo].t_s - t ? lo - 1 : lo; };

  /* =========================================================================
     Trạng thái trực tiếp: WebSocket /api/ws (qua được Cloudflare quick tunnel), tự nối lại sau 1 s
     ========================================================================= */
  let L = { state: "idle", events: [] }, hist = [], histRun = null, liveDirty = false, wsUp = false;
  let heard;   // khoá câu nói cuối đã xử lý; undefined = chưa nhận bản tin nào (mở trang giữa lần chạy: không phát lại câu cũ)
  api.history().then((h) => { if (!hist.length && h.run_id) { histRun = h.run_id; hist = h.samples.map(toPt); } }).catch(() => {});
  function toPt(s) { return { t: s.t_s, gap: s.gap_m, thr: s.threshold_m, ttc: s.ttc_s }; }
  function connect() {
    const w = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/ws`);
    w.onopen = () => { wsUp = true; streamRun = null; };   // nối lại (server khởi động lại): gắn lại luồng ảnh ở lần vẽ sau
    w.onmessage = (m) => onStatus(JSON.parse(m.data));
    w.onclose = () => { wsUp = false; setTimeout(connect, 1000); };
  }
  function onStatus(s) {
    const prevState = L.state;
    if (s.run_id !== histRun) { hist = []; histRun = s.run_id; if (heard !== undefined) heard = null; }
    if (s.sample && (!hist.length || hist[hist.length - 1].t !== s.sample.t_s)) { hist.push(toPt(s.sample)); if (hist.length > 600) hist.shift(); }
    L = s;
    // phát câu vừa nói (chỉ câu mới, chỉ khi đang chạy, chỉ khi người xem bật âm thanh)
    const ev = s.events || [], e = ev[ev.length - 1], key = e ? `${s.run_id}/${e.t_s}/${e.kind}` : null;
    if (key !== heard) {
      const stale = heard === undefined; heard = key;
      if (e && !stale) { flashSay(); if (sound && s.state === "running") speak(e.kind, () => { $("say-t").textContent = "Chưa có file âm thanh (models/phrases-demo/)"; }); }
    }
    if (prevState !== s.state && ["done", "stopped", "failed"].includes(s.state)) { if (route === "runs") renderRuns(); if (route === "upload") renderRecent(); }
    if (route === "live" && !liveDirty) { liveDirty = true; requestAnimationFrame(() => { liveDirty = false; renderLive(); }); }
  }
  function flashSay() { const el = $("say"); el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }

  // Phát theo danh sách câu đã nói (events) thay vì decision.say của từng tin: tin nào bị gộp khi server xử lý nhanh
  // hơn tốc độ gửi thì câu nói vẫn không bị bỏ sót.
  /* ---------- màn Lái thử ---------- */
  let streamRun = null, resultUrl = null;
  /* WebRTC truyền video liên tục; WebSocket vẫn cập nhật số đo và cảnh báo. */
  let rtcSession = null, rtcRetry = 0, rtcLabel = "Đang nối video…", rtcPlaying = false;
  /* Chưa có khung WebRTC (đang nối, dò ICE, thử lại): hiện ảnh JPEG mới nhất của /api/frame để màn hình không đen. */
  let stillGrab = 0, stillShown = null;
  function stillStart() {
    if (stillGrab) return;
    const token = stillGrab = Date.now(), img = $("still"), next = (ms) => { if (stillGrab === token) setTimeout(grab, ms); };
    async function grab() {   // ảnh sau chỉ xin khi ảnh trước đã hiện, như ảnh trực tiếp ở Lab
      try {
        const r = await fetch(`/api/frame?t=${Date.now()}`, { cache: "no-store" });
        if (r.status !== 200) return next(300);
        const url = URL.createObjectURL(await r.blob()), pre = new Image(); pre.src = url; await pre.decode();
        if (stillGrab !== token) { URL.revokeObjectURL(url); return; }
        img.src = url; if (stillShown) URL.revokeObjectURL(stillShown); stillShown = url; next(100);
      } catch { next(300); }
    }
    grab();
  }
  function stillStop() {
    stillGrab = 0; $("still").hidden = true; $("still").removeAttribute("src");
    if (stillShown) { URL.revokeObjectURL(stillShown); stillShown = null; }
  }
  $("stream").addEventListener("playing", () => { rtcPlaying = true; if (route === "live") renderLive(); });
  function releasePeer(id) {
    if (id) fetch(`/api/rtc/${id}`, { method: "DELETE", keepalive: true }).catch(() => {});
  }
  function detachStream() {
    streamRun = null; rtcPlaying = false; clearTimeout(rtcRetry);
    const session = rtcSession; rtcSession = null;
    if (session) {
      clearTimeout(session.timer); session.abort.abort();
      session.pc.close(); releasePeer(session.peerId);
    }
    $("stream").srcObject = null;
  }
  async function gatherIce(pc, signal) {
    if (pc.iceGatheringState === "complete") return;
    await new Promise((resolve, reject) => {
      const finish = (error) => {
        clearTimeout(timer); pc.removeEventListener("icegatheringstatechange", changed);
        signal.removeEventListener("abort", aborted); error ? reject(error) : resolve();
      };
      const changed = () => { if (pc.iceGatheringState === "complete") finish(); };
      const aborted = () => finish(new Error("Đã ngắt video"));
      const timer = setTimeout(() => finish(new Error("Không tìm được đường truyền video")), 12000);
      pc.addEventListener("icegatheringstatechange", changed);
      signal.addEventListener("abort", aborted, { once: true });
      if (signal.aborted) aborted();
    });
  }
  async function attachStream(runId) {
    detachStream(); streamRun = runId; rtcLabel = "Đang nối video…";
    if (!window.RTCPeerConnection) { rtcLabel = "Trình duyệt chưa hỗ trợ video trực tiếp"; return; }
    const pc = new RTCPeerConnection(), abort = new AbortController();
    const session = { pc, abort, peerId: null, timer: 0 }; rtcSession = session;
    const current = () => rtcSession === session;
    const retry = () => {
      if (!current()) return;
      detachStream(); streamRun = runId;
      rtcLabel = "Chưa nối được video · kiểm tra mạng hoặc TURN";
      $("screen-tag").textContent = rtcLabel;
      rtcRetry = setTimeout(() => { if (streamRun === runId) attachStream(runId); }, 5000);
    };
    session.timer = setTimeout(retry, 25000);
    pc.ontrack = (e) => {
      if (!current()) return;
      $("stream").srcObject = e.streams[0] || new MediaStream([e.track]);
      $("stream").play().catch(() => { if (current()) retry(); });
    };
    pc.onconnectionstatechange = () => {
      if (!current()) return;
      if (pc.connectionState === "connected") {
        clearTimeout(session.timer); rtcLabel = "Trực tiếp"; $("screen-tag").textContent = rtcLabel;
      } else if (["failed", "disconnected"].includes(pc.connectionState)) retry();
    };
    try {
      const config = await call("/api/rtc", { signal: abort.signal });
      if (!current()) return;
      pc.setConfiguration(config);
      pc.addTransceiver("video", { direction: "recvonly" });
      await pc.setLocalDescription(await pc.createOffer());
      await gatherIce(pc, abort.signal);
      const answer = await call("/api/rtc/offer", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: abort.signal,
        body: JSON.stringify({ run_id: runId, type: pc.localDescription.type, sdp: pc.localDescription.sdp })
      });
      if (!current()) { releasePeer(answer.peer_id); return; }
      session.peerId = answer.peer_id;
      await pc.setRemoteDescription({ type: answer.type, sdp: answer.sdp });
    } catch { retry(); }
  }
  window.addEventListener("pagehide", detachStream);
  function renderLive() {
    const s = L, m = s.measure || null, d = s.decision || null, lead = m ? m.lead : null, cal = m ? m.calibration : null;
    const active = s.state === "loading" || s.state === "running";
    // màn hình: WebRTC khi đang chạy, video đã chú thích khi xong
    const img = $("stream"), vid = $("result"), empty = $("screen-empty");
    if (active) {
      if (streamRun !== s.run_id) attachStream(s.run_id);
      if (rtcPlaying) stillStop(); else stillStart();
      img.hidden = !rtcPlaying; $("still").hidden = rtcPlaying; vid.hidden = true; empty.hidden = true;
      $("screen-tag").textContent = s.state === "loading" ? "Đang chuẩn bị video…" : rtcLabel;
    } else {
      detachStream(); stillStop(); img.hidden = true;
      const url = s.outputs && s.outputs.video_url;
      if (url) { if (resultUrl !== url) { vid.src = url; resultUrl = url; } vid.hidden = false; empty.hidden = true; $("screen-tag").textContent = "Video đã chú thích"; }
      else {
        vid.hidden = true; empty.hidden = false; $("screen-tag").textContent = "Kính lái";
        empty.querySelector("b").textContent = s.state === "failed" ? "Lần chạy lỗi" : s.state === "stopped" ? "Đã dừng" : "Chưa có lần chạy";
        empty.querySelector("span").textContent = s.state === "failed" ? (s.error || "Không rõ lỗi") : "Tải một video ở trang Chạy video, hoặc chọn video mẫu.";
      }
    }
    const pill = $("run-state");
    pill.querySelector(".dot").className = "dot " + ({ running: "run", loading: "run", done: "ok", stopped: "warn", failed: "bad" }[s.state] || "");
    pill.lastElementChild.textContent = (STATE_VI[s.state] || s.state) + (wsUp ? "" : " · mất kết nối");
    const ops = s.ops || null;   // tốc độ xử lý như trang upload của comma: ≥ fps của video là theo kịp thời gian thực
    $("run-time").textContent = m ? `t = ${fmtT(m.t_s)} · khung ${ni(m.frame)}${ops ? ` · xử lý ${nf(ops.fps, 0)} fps` : ""}` : "—";
    $("run-time").title = ops && isNum(ops.video_fps) ? `Tốc độ xử lý; video gốc ${nf(ops.video_fps, 0)} fps, lớn hơn hoặc bằng là theo kịp thời gian thực` : "";
    $("stop").disabled = !active;
    const gap = lead ? lead.gap_m : null, thr = d ? d.threshold_m : null, ttc = m ? m.ttc_s : null, level = d ? d.level : null;
    // ô Đo khoảng cách: khoảng cách so với ngưỡng luật, phát hiện xe phía trước, TTC, tốc độ xe mình
    $("m-gap").textContent = isNum(gap) ? `${nf(gap)} m` : "—";
    $("m-thr").textContent = isNum(thr) ? `${nf(thr, 0)} m` : "—";
    $("m-thr-s").textContent = isNum(thr) ? (isNum(gap) ? (gap < thr ? `hẹp hơn ${nf(thr - gap)} m` : `dư ${nf(gap - thr)} m`) : "") : d ? "dưới 60 km/h: luật không đặt ngưỡng" : "";
    $("m-gap-box").classList.toggle("below", isNum(gap) && isNum(thr) && gap < thr);
    const scale = Math.max(100, isNum(thr) ? thr * 1.6 : 0, isNum(gap) ? gap * 1.1 : 0);
    $("m-bar").style.width = isNum(gap) ? `${Math.min(100, gap / scale * 100)}%` : "0";
    $("m-bar").classList.toggle("below", isNum(gap) && isNum(thr) && gap < thr);
    $("m-mark").hidden = !isNum(thr); if (isNum(thr)) $("m-mark").style.left = `${thr / scale * 100}%`;
    // BT-A chỉ nhận xe dẫn đầu cùng làn, qua giai đoạn khởi động và có trễ chống chập chờn: model có thể tin là có xe
    // mà chưa có khoảng cách
    const seen = !!lead && lead.prob >= 0.5;
    $("m6-lead").textContent = !lead ? "xe phía trước: _" : `xe phía trước: ${isNum(gap) ? "có" : seen ? "chưa nhận" : "không thấy"} · tin cậy ${nf(lead.prob, 2)}`
      + (!isNum(gap) && seen ? " · chưa đủ điều kiện xe cùng làn" : "");
    const gs = m ? m.gps : null;
    // có log GPS: sáu ô như trang Lab (khoảng cách model | radar | Δ, tốc độ model | log | Δ); thiếu số nào thì "_"
    const none = "_", sgn = (v) => v >= 0 ? "+" : "";
    const est = m ? m.model_kmh : null, real = m ? m.gps_kmh : null, rad = m ? m.radar_m : null;
    $("m6-dist").textContent = isNum(gap) ? `${nf(gap)} m` : none;
    $("m6-radar").textContent = isNum(rad) ? `${nf(rad)} m` : none;
    $("m6-ddist").textContent = isNum(gap) && isNum(rad) ? `${sgn(gap - rad)}${nf(gap - rad)} m` : none;
    $("m6-ego").textContent = isNum(est) ? `${nf(est, 0)} km/h` : none;
    $("m6-log").textContent = isNum(real) ? `${nf(real, 0)} km/h` : none;
    $("m6-dspeed").textContent = isNum(est) && isNum(real) ? `${sgn(est - real)}${nf(est - real, 0)} km/h` : none;
    $("gps-dot").className = "dot " + (!gs || gs.state === "none" ? "" : gs.state === "synced" ? "ok" : gs.state === "syncing" ? "warn" : "bad");
    $("gps-text").textContent = "GPS: " + (!gs ? "—" : gs.state === "none" ? "không có log" : gs.state === "syncing" ? "đang đồng bộ (cần ~20 s xe chạy)"
      : `lệch ${gs.offset_s >= 0 ? "+" : ""}${nf(gs.offset_s, 2)} s` + (isNum(gs.corr) ? ` (tương quan ${nf(gs.corr, 2)})` : " (dùng thẳng log, coi như log bắt đầu cùng video)") + (gs.state === "low_confidence" ? ", không tin cậy" : ""));
    $("cal-flags").textContent = cal ? flagText(cal.flags) : "";
    // cột HUD (đang tạm tắt trong index.html): tốc độ, trạng thái, sơ đồ làn, mức cảnh báo
    $("h-speed").textContent = nf(m && m.ego_kmh, 0);
    $("h-state").dataset.state = s.state;
    $("h-state").lastElementChild.textContent = `Chạy cục bộ · ${(STATE_VI[s.state] || s.state)}${wsUp ? "" : " · mất kết nối"}`;
    $("h-gap").textContent = isNum(gap) ? `${nf(gap)} m` : "—";
    $("h-gap-box").classList.toggle("hot", isNum(gap) && isNum(thr) && gap < thr);
    $("h-thr").textContent = isNum(thr) ? `${nf(thr, 0)} m` : "—";
    $("h-thr-s").textContent = isNum(thr) || !d ? "ngưỡng luật" : "ngưỡng: dưới 60 km/h";
    // phát hiện: có xe dẫn đầu khi BT-A trả khoảng cách (prob đủ ngưỡng)
    $("h-lead").textContent = !lead ? "—" : isNum(gap) ? "Có" : "Không";
    $("h-prob").textContent = !lead ? "xe phía trước" : `xe trước · tin cậy ${nf(lead.prob, 2)}`;
    $("h-ttc").textContent = isNum(ttc) ? `${nf(ttc)} s` : "—";
    $("h-ttc-box").classList.toggle("hot", isNum(ttc) && !!cfg && ttc <= cfg.ttc_emergency_s);
    const ha = $("h-alert"); ha.dataset.level = level || "";
    $("h-alert-t").textContent = level ? LEVEL_VI[level] : "Không có cảnh báo";
    $("h-alert-s").textContent = level ? `“${cfg && cfg.phrases ? cfg.phrases[level] : ""}”` : active ? "RoadWatch đang im lặng" : "Chưa chạy";
    drawLane($("h-lane"), { gap, thr, level });
    // quyết định BT-B
    $("decision").dataset.level = (d && d.level) || "";
    document.querySelectorAll("#decision .lamp").forEach((el) => el.classList.toggle("on", !!d && el.dataset.l === d.level));
    const ev = s.events || [], last = ev[ev.length - 1];
    $("say-q").textContent = last ? `“${last.text}”` : "Im lặng";
    if (!phrasesMissing || !sound) $("say-t").textContent = last ? `${LEVEL_VI[last.kind]} · lúc ${fmtT(last.t_s)}` : "";
    $("why").textContent = d ? d.reason : s.state === "failed" ? (s.error || "—") : "—";
    // hiệu chuẩn camera
    const cs = cal ? cal.status : null, k = /(\d+)\/(\d+)/.exec(cs || "");
    $("cal-dot").className = "dot " + (!cs ? "" : cs === "calibrated" && cal.calibrated ? "ok" : cs.startsWith("unreliable") ? "bad" : "warn");
    $("cal-text").textContent = "Hiệu chuẩn camera: " + (!cs ? "—" : cs === "calibrated" ? (cal.calibrated ? "xong" : "xong, đang học tiêu cự") : k ? `đang hiệu chuẩn ${k[1]}/${k[2]}` : cs.replace(/^unreliable:?\s*/, "không tin cậy: "));
    // câu đã nói
    $("events").innerHTML = ev.length ? ev.slice().reverse().map((e) =>
      `<li><span class="k">${fmtT(e.t_s)}</span><span><span class="tag ${e.kind}">${LEVEL_VI[e.kind]}</span> “${esc(e.text)}”<br><span class="r">${esc(e.reason)}</span></span></li>`).join("")
      : `<li class="none muted">Chưa nói câu nào.</li>`;
    const out = s.outputs;
    $("live-files").hidden = !out;
    if (out) { $("live-video-dl").href = out.video_url; $("live-video-dl").download = `${s.run_id}.mp4`; $("live-log-dl").href = out.log_url; $("live-log-dl").download = `${s.run_id}-decisions.json`; }
    showResult("live", out && out.csv_url ? { run_id: s.run_id, csv_url: out.csv_url, calibration_url: out.calibration_url } : null);
    const tEnd = hist.length ? hist[hist.length - 1].t : 30;
    scenes.live.redraw();
    drawChart($("live-chart"), hist, { t0: Math.max(0, tEnd - 30), t1: Math.max(30, tEnd), thr: true, events: ev });
  }
  /* Sơ đồ làn nhìn từ trên trong cột HUD: làn của xe mình vẽ phối cảnh, xe mình ở dưới, xe phía trước đặt theo khoảng cách
     đo được (thang 0..max(80, 1,4 × ngưỡng) m), vạch ngưỡng luật ngang làn. Chỉ có xe dẫn đầu: BT-A không đo vật khác. */
  function drawLane(cv, { gap, thr, level }) {
    const dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
    if (!W || !H) return;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    const top = H * 0.06, bot = H * 0.98, egoY = H * 0.8, cx = W / 2, wTop = W * 0.1, wBot = W * 0.62;
    const span = Math.max(80, isNum(thr) ? thr * 1.4 : 0);
    const Y = (m) => egoY - (egoY - top) * (1 - Math.pow(1 - Math.min(1, m / span), 1.6));   // xa thì dồn lại: cảm giác phối cảnh
    const half = (y) => wTop / 2 + (wBot - wTop) / 2 * (y - top) / (bot - top);
    // mặt làn và hai vạch phát sáng
    const road = g.createLinearGradient(0, top, 0, bot); road.addColorStop(0, "rgba(46,120,220,0)"); road.addColorStop(1, "rgba(46,120,220,.22)");
    g.fillStyle = road; g.beginPath(); g.moveTo(cx - half(top), top); g.lineTo(cx + half(top), top); g.lineTo(cx + half(bot), bot); g.lineTo(cx - half(bot), bot); g.fill();
    g.save(); g.shadowColor = "#3aa0ff"; g.shadowBlur = 10; g.lineWidth = 3;
    for (const sd of [-1, 1]) {
      const lg = g.createLinearGradient(0, top, 0, bot); lg.addColorStop(0, "rgba(80,170,255,0)"); lg.addColorStop(1, "rgba(80,170,255,.95)");
      g.strokeStyle = lg; g.beginPath(); g.moveTo(cx + sd * half(top), top); g.lineTo(cx + sd * half(bot), bot); g.stroke();
    }
    g.restore();
    const box = (y, s, fill, stroke) => { const w = 34 * s, h = 46 * s; g.fillStyle = fill; g.strokeStyle = stroke; g.lineWidth = 1.5;
      g.beginPath(); g.roundRect(cx - w / 2, y - h, w, h, 7 * s); g.fill(); g.stroke();
      g.fillStyle = "rgba(10,20,35,.7)"; g.beginPath(); g.roundRect(cx - w * 0.36, y - h * 0.78, w * 0.72, h * 0.3, 4 * s); g.fill();
      g.fillStyle = "#ff4d4f"; g.fillRect(cx - w * 0.42, y - h * 0.16, w * 0.18, h * 0.07); g.fillRect(cx + w * 0.24, y - h * 0.16, w * 0.18, h * 0.07); };
    const sc = (y) => 0.45 + 0.55 * (y - top) / (egoY - top);
    // vạch ngưỡng luật
    if (isNum(thr)) {
      const y = Y(thr), hw = half(y) + 6, below = isNum(gap) && gap < thr;
      g.fillStyle = below ? "rgba(224,140,30,.18)" : "rgba(200,150,40,.1)";
      g.beginPath(); g.moveTo(cx - hw, y); g.lineTo(cx + hw, y); g.lineTo(cx + half(egoY) + 6, egoY); g.lineTo(cx - half(egoY) - 6, egoY); g.fill();
      g.strokeStyle = "#e8b04a"; g.setLineDash([5, 4]); g.lineWidth = 2; g.beginPath(); g.moveTo(cx - hw, y); g.lineTo(cx + hw, y); g.stroke(); g.setLineDash([]);
      g.fillStyle = "#e8b04a"; g.font = "600 10px ui-monospace, Consolas, monospace"; g.textAlign = "left"; g.textBaseline = "middle"; g.fillText(`${nf(thr, 0)} m`, cx + hw + 4, y);
    }
    // xe phía trước
    if (isNum(gap)) {
      const y = Y(gap), col = level ? COLOR[level] : "#9fb3c8";
      g.strokeStyle = col; g.globalAlpha = 0.8; g.setLineDash([2, 4]); g.lineWidth = 1.5; g.beginPath(); g.moveTo(cx, egoY - 50); g.lineTo(cx, y); g.stroke(); g.setLineDash([]); g.globalAlpha = 1;
      box(y, sc(y), level ? rgba(COLOR[level], 0.85) : "rgba(150,170,190,.85)", col);
      const label = `${nf(gap)} m`; g.font = "600 11px ui-monospace, Consolas, monospace";       // nhãn có nền: đọc được cả khi đè ảnh vật thể
      const tw = g.measureText(label).width + 12, lx = Math.max(2, cx - half(y) - 10 - tw), ly = y - 18 * sc(y);
      g.fillStyle = "rgba(6,17,31,.92)"; g.strokeStyle = col; g.lineWidth = 1.2; g.beginPath(); g.roundRect(lx, ly - 9, tw, 18, 9); g.fill(); g.stroke();
      g.fillStyle = "#e6edf3"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(label, lx + tw / 2, ly + 0.5);
    } else {
      g.fillStyle = "#7f93a8"; g.font = "11px system-ui, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("Không thấy xe phía trước", cx, H * 0.35);
    }
    // xe mình
    g.save(); g.shadowColor = "rgba(70,214,230,.6)"; g.shadowBlur = 16; box(egoY + 46, 1, "#e9eef3", "#ffffff"); g.restore();
  }

  /* =========================================================================
     Chạy video
     ========================================================================= */
  const VIDEO_EXT = [".mp4", ".mov", ".mkv", ".avi", ".hevc", ".h264", ".webm"];
  let picked = null, pvUrl = null, pvAuto;   // pvAuto: vùng camera tự dò [x, y, w, h]; undefined = đang dò, null = không dò được
  const pvVideo = $("pv-video"), pvThumb = $("pv-thumb");
  const fmtSize = (b) => b >= 1073741824 ? `${nf(b / 1073741824, 1)} GB` : `${nf(b / 1048576, 1)} MB`;
  const setStep = (n) => { for (const li of $("stepper").children) { const k = Number(li.dataset.n);
    li.classList.toggle("done", k < n); k === n ? li.setAttribute("aria-current", "step") : li.removeAttribute("aria-current"); } };
  function clearPick() {
    picked = null; $("file").value = ""; setStep(1);
    if (pvUrl) URL.revokeObjectURL(pvUrl); pvUrl = null;
    pvVideo.pause(); pvVideo.removeAttribute("src"); pvVideo.load();
    $("pv").hidden = true; $("pv-empty").hidden = false; pvAuto = undefined; $("pv-box").hidden = true; $("pv-crop").textContent = "";
  }
  /* Tốc độ khung của video: model đo vận tốc từ thời gian giữa hai khung, nên fps nhập sai thì vận tốc sai theo tỉ lệ.
     Lệch quá 5 % thì hiện hộp thoại: dùng giá trị đo được, hoặc giữ giá trị đã nhập (cố ý) rồi mới gửi tiếp. */
  let videoFps = null, fpsKeep = false;
  const fpsVi = (x) => String(x).replace(".", ",");
  async function fpsMismatch() {
    if (videoFps === null || fpsKeep) return false;
    const { fpsHint } = await import("/ui/fpsprobe.mjs");
    return fpsHint(videoFps, Number($("fps").value));
  }
  /** Hộp thoại; trả về true khi người dùng đã chọn (dùng hoặc giữ), false khi không có gì lệch. */
  async function askFps() {
    const h = await fpsMismatch();
    if (!h || h.ok) return false;
    const dlg = $("fps-dialog"), entered = Number($("fps").value);
    $("fps-dialog-p").textContent = h.text;
    $("fps-use").textContent = `Dùng ${fpsVi(videoFps)}`; $("fps-keep").textContent = `Giữ ${Number.isFinite(entered) ? fpsVi(entered) : "giá trị đã nhập"}`;
    if (typeof dlg.showModal !== "function") return false;   // trình duyệt cũ: bỏ qua, server vẫn gắn cờ
    await new Promise((resolve) => { dlg.addEventListener("close", resolve, { once: true }); dlg.showModal(); });
    if (dlg.returnValue === "use") $("fps").value = videoFps; else fpsKeep = true;
    return true;
  }
  async function probeFps(f) {
    videoFps = null; fpsKeep = false;
    try {
      const { measureFps } = await import("/ui/fpsprobe.mjs"), url = URL.createObjectURL(f);
      const v = await measureFps(url); URL.revokeObjectURL(url);
      if (picked !== f) return;
      videoFps = v;
    } catch { videoFps = null; }
    if (picked === f) await askFps();
  }
  function pick(f) {
    if (!f) return;
    clearPick(); picked = f; $("form-error").textContent = ""; setStep(2);
    $("pv-empty").hidden = true; $("pv").hidden = false;
    $("pv-name").textContent = f.name; $("pv-meta").textContent = fmtSize(f.size); $("pv-res").textContent = "Đang đọc thông tin video…";
    pvThumb.classList.remove("playing", "na"); pvVideo.controls = false;
    pvUrl = URL.createObjectURL(f); pvVideo.src = pvUrl;
    probeFps(f);
    detectBox(pvUrl).then((b) => {
      if (picked !== f) return;
      pvAuto = b;
      lensUi();
    }).catch(() => { if (picked === f) { pvAuto = null; lensUi(); } });
  }
  /* Bản JS của model.detect_content_box (comma realtime_lead): trung vị theo thời gian của 15 khung xám; hàng / cột có
     trung vị < 24 là viền đen; chỉ cắt khi có viền ở cả hai phía đối diện với cỡ gần bằng nhau (video đã chèn viền),
     còn nắp capo tối hay trời đêm chỉ ở một phía thì giữ. Server tự dò lại khi chạy; ở đây để xem trước và điền sẵn. */
  async function detectBox(url, samples = 15) {
    const v = document.createElement("video"); v.muted = true; v.preload = "auto"; v.src = url;
    await new Promise((ok, no) => { v.onloadedmetadata = ok; v.onerror = no; });
    const W = v.videoWidth, H = v.videoHeight; if (!W) throw new Error("no video");
    const k = Math.max(1, Math.ceil(Math.max(W, H) / 1280)), w = Math.round(W / k), h = Math.round(H / k), n = w * h;   // video rất lớn: dò trên ảnh thu nhỏ
    const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
    const g = cv.getContext("2d", { willReadFrequently: true }), stack = [];
    const dur = isFinite(v.duration) ? v.duration : 0;
    for (let s = 0; s < samples; s++) {
      await new Promise((ok, no) => { const t = setTimeout(() => no(new Error("seek")), 5000); v.onseeked = () => { clearTimeout(t); ok(); }; v.currentTime = 0.001 + Math.max(0, dur - 0.1) * s / (samples - 1); });
      g.drawImage(v, 0, 0, w, h);
      const d = g.getImageData(0, 0, w, h).data, gray = new Uint8Array(n);
      for (let i = 0; i < n; i++) gray[i] = (d[4 * i] * 299 + d[4 * i + 1] * 587 + d[4 * i + 2] * 114) / 1000;
      stack.push(gray);
    }
    v.removeAttribute("src"); v.load();
    const median = (a) => { const q = Float32Array.from(a).sort(), m = q.length; return m % 2 ? q[(m - 1) / 2] : (q[m / 2 - 1] + q[m / 2]) / 2; };
    const med = new Float32Array(n), buf = new Array(stack.length);
    for (let i = 0; i < n; i++) { for (let j = 0; j < stack.length; j++) buf[j] = stack[j][i]; med[i] = median(buf); }
    const bars = (line, size) => {
      const bar = line.map((x) => x < 24), all = bar.every(Boolean);
      const lead = all ? size : bar.indexOf(false), trail = all ? size : bar.slice().reverse().indexOf(false);
      return lead && trail && Math.abs(lead - trail) <= 0.25 * Math.max(lead, trail) + 16 / k && lead + trail < 0.8 * size ? [lead, size - trail] : [0, size];
    };
    const rows = Array.from({ length: h }, (_, y) => median(med.subarray(y * w, (y + 1) * w)));
    const [y0, y1] = bars(rows, h);
    const cols = Array.from({ length: w }, (_, x) => { const c = []; for (let y = y0; y < y1; y++) c.push(med[y * w + x]); return median(c); });
    const [x0, x1] = bars(cols, w);
    const X0 = x0 * k, Y0 = y0 * k, X1 = x1 === w ? W : x1 * k, Y1 = y1 === h ? H : y1 * k;
    const ex = X0 + X0 % 2, ey = Y0 + Y0 % 2;   // chẵn: mặt phẳng U, V có nửa kích thước
    return [ex, ey, Math.floor((X1 - ex) / 2) * 2, Math.floor((Y1 - ey) / 2) * 2];
  }
  function cropBox() {   // vùng ảnh camera sẽ đưa vào model (tự dò viền đen); null khi chưa biết
    return pvVideo.videoWidth ? pvAuto || null : null;
  }
  function drawBox() {   // khung xanh trên ảnh xem trước, như trang upload của comma ("Khung xanh = vùng đưa vào model")
    const b = cropBox(), el = $("pv-box"), W = pvVideo.videoWidth, H = pvVideo.videoHeight;
    el.hidden = !b || !picked;
    $("pv-crop").textContent = !picked ? "" : b ? `Vùng camera: x=${b[0]}, y=${b[1]}, ${b[2]}×${b[3]} (khung xanh)`
      : pvAuto === undefined ? "Đang dò vùng camera…" : "Trình duyệt không dò được vùng camera; server tự dò khi chạy.";
    if (el.hidden) return;
    const tw = pvThumb.clientWidth, th = pvThumb.clientHeight, s = Math.max(tw / W, th / H), ox = (tw - W * s) / 2, oy = (th - H * s) / 2;   // object-fit: cover
    Object.assign(el.style, { left: `${ox + b[0] * s}px`, top: `${oy + b[1] * s}px`, width: `${b[2] * s}px`, height: `${b[3] * s}px` });
  }
  /* Thông số ống kính: như trang upload của comma_ai/lead_distance (pages/Upload_video.py) */
  const EQUIV_WIDTH_MM = 34.6;
  /* Góc nhìn ngang ngoài 30–150° gần như chắc là nhập nhầm (vd. 26 mm "tương đương" mà chọn "tiêu cự thật" → ~12°):
     model chỉ thấy một vùng hẹp giữa ảnh, không ra làn hay xe */
  const fovWarn = (W, f) => {
    const deg = 2 * Math.atan(W / 2 / f) * 180 / Math.PI;
    return deg >= 30 && deg <= 150 ? "" : ` ⚠ Góc nhìn ngang ≈ ${Math.round(deg)}°: camera hành trình / điện thoại thường 60–120°. Kiểm tra lại "Tiêu cự tương đương" hay "Tiêu cự thật".`;
  };
  function lensUi() {
    const lens = $("lens").value, real = $("mm-kind").value === "real", own = $("fov-preset").value === "";
    document.querySelectorAll("[data-lens]").forEach((el) => {
      const k = el.dataset.lens;
      el.hidden = !(k === lens || (k === "mm-real" && lens === "mm" && real) || (k === "fov-own" && lens === "fov" && own));
    });
    $("f-mm-l").textContent = real ? "Tiêu cự thật" : "Tiêu cự tương đương";
    $("mm-hint").textContent = real ? "Camera / dashcam: nhập tiêu cự thật trong thông số kỹ thuật, kèm chiều rộng cảm biến ở ô bên dưới." : "Điện thoại thường ghi tương đương 35 mm: camera chính 26 mm, góc rộng 13 mm, tele 77 mm.";
    // tiêu cự px tương ứng, theo vùng ảnh camera (cả khung video khi chưa dò xong; server tính lại sau khi cắt viền)
    const b = cropBox(), W = b ? b[2] : pvVideo.videoWidth, H = b ? b[3] : pvVideo.videoHeight, num = (id) => Number($(id).value);
    let f = null;
    if (lens === "mm" && W) f = num("f-mm") * Math.max(W, H) / (real ? num("sensor-mm") : EQUIV_WIDTH_MM);
    if (lens === "fov" && W) { const [kind, deg] = own ? [$("fov-lens").value, num("hfov")] : $("fov-preset").value.split(":");
      const half = Number(deg) * Math.PI / 360; f = W / 2 / (kind === "fisheye" ? half : Math.tan(half)); }
    $("lens-px").textContent = lens === "learn" ? "Tiêu cự học từ ~10 s đầu xe chạy; cảnh báo khoảng cách chỉ bật khi học xong. Học sai nếu xe chậm hoặc video cắt ghép."
      : isNum(f) && f > 0 ? `→ tiêu cự ≈ ${ni(Math.round(f))} px (cạnh dài ảnh camera ${ni(Math.max(W, H))} px). Chỉ đúng nếu video không bị crop / zoom số / chống rung điện tử.` + fovWarn(W, f) : "";
    drawBox();
  }
  const FLAG_VI = {
    auto_focal_needs_gps: "Tự hiệu chỉnh tiêu cự cần log GPS; đã dùng thông số nhập tay.",
    gps_sync_low_confidence: "Không đồng bộ được GPS với video (tương quan < 0.8); dùng độ lệch đã nhập/0.",
    focal_calibrating: "Thang đo (tiêu cự) chưa hiệu chỉnh xong theo GPS.",
    fps_differs_from_video: "Tốc độ khung nhập khác tốc độ khung của video (lệch quá 5 %): vận tốc đo từ thời gian giữa hai khung nên sẽ sai theo tỉ lệ đó. Chạy lại với fps đúng.",
  };
  const flagText = (flags) => (flags || []).map((f) => FLAG_VI[f] || f).join(" ");

  function wireUpload() {
    const drop = $("drop");
    for (const id of ["lens", "mm-kind", "f-mm", "sensor-mm", "fov-preset", "fov-lens", "hfov", "fy", "gps-file", "radar-file"])
      $(id).addEventListener("input", lensUi);
    new ResizeObserver(drawBox).observe(pvThumb);
    pvVideo.addEventListener("loadedmetadata", lensUi);
    lensUi();
    pvVideo.addEventListener("loadedmetadata", () => {
      if (!picked) return;
      if (isFinite(pvVideo.duration)) { $("pv-meta").textContent = `${fmtSize(picked.size)} · ${fmtT(pvVideo.duration).replace(/\.\d$/, "")}`; pvVideo.currentTime = Math.min(1, pvVideo.duration / 2); }
      $("pv-res").textContent = pvVideo.videoWidth ? `${pvVideo.videoWidth}×${pvVideo.videoHeight}` : "Độ phân giải: chưa đọc được";
    });
    pvVideo.addEventListener("error", () => { if (picked) { pvThumb.classList.add("na"); $("pv-res").textContent = "Độ phân giải: chưa đọc được"; } });
    $("pv-play").addEventListener("click", () => { pvThumb.classList.add("playing"); pvVideo.controls = true; pvVideo.play().catch(() => {}); });
    $("pv-del").addEventListener("click", clearPick);
    $("pv-swap").addEventListener("click", () => $("file").click());
    $("file").addEventListener("change", () => pick($("file").files[0]));
    $("fps").addEventListener("input", () => { fpsKeep = false; });
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", (e) => pick(e.dataTransfer.files[0]));
    $("upload-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      if (await askFps()) return;   // tốc độ khung lệch: hỏi trước; người dùng chọn xong thì bấm gửi lại
      const num = (id) => { const v = $(id).value.trim(); return v === "" ? null : Number(v); };
      const fps = num("fps"), d = num("d"), lens = $("lens").value, fy = num("fy");
      const real = $("mm-kind").value === "real", own = $("fov-preset").value === "";
      const check = (id, ok, msg) => { $(`e-${id}`).textContent = ok ? "" : msg; return ok; };
      check("fps", isNum(fps) && fps > 0 && fps <= 240, "Nhập số lớn hơn 0 và không quá 240.");
      check("d", isNum(d) && d >= 0 && d <= 5, "Nhập số từ 0 đến 5 mét.");
      check("fy", lens !== "px" || (isNum(fy) && fy > 0 && fy <= 10000), "Nhập số lớn hơn 0 và không quá 10000.");
      check("f-mm", lens !== "mm" || (num("f-mm") > 0 && num("f-mm") <= 300), "Nhập tiêu cự lớn hơn 0 và không quá 300 mm.");
      check("sensor-mm", lens !== "mm" || !real || (num("sensor-mm") > 0 && num("sensor-mm") <= 40), "Nhập chiều rộng cảm biến từ 0 đến 40 mm.");
      check("hfov", lens !== "fov" || !own || (num("hfov") >= 20 && num("hfov") <= 170), "Nhập góc từ 20 đến 170 độ.");
      const gpsFile = $("gps-file").files[0];
      const radarFile = $("radar-file").files[0];
      if (!picked) { $("form-error").textContent = "Chưa chọn video. Kéo thả file vào ô bên trái, hoặc chọn một video mẫu."; drop.classList.remove("attn"); void drop.offsetWidth; drop.classList.add("attn"); return; }
      const ext = (picked.name.toLowerCase().match(/\.[a-z0-9]+$/) || [""])[0];
      if (!VIDEO_EXT.includes(ext)) { $("form-error").textContent = `Định dạng chưa hỗ trợ. Dùng ${VIDEO_EXT.join(", ")}.`; return; }
      if ([...document.querySelectorAll("#upload-form .err")].some((el) => el.textContent)) return;
      const q = { name: picked.name, fps, d, rt: true, lens };
      if (lens === "px") q.fy = fy;
      if (lens === "mm") { q.f_mm = num("f-mm"); if (real) q.sensor_mm = num("sensor-mm"); }
      if (lens === "fov") { const [kind, deg] = own ? [$("fov-lens").value, num("hfov")] : $("fov-preset").value.split(":"); q.hfov = Number(deg); q.fisheye = kind === "fisheye"; }
      setStep(3); $("submit").disabled = true; pvVideo.pause(); $("form-error").textContent = ""; $("up-prog").hidden = false;
      const prog = (f, bps, left) => {
        $("up-bar").style.width = `${f * 100}%`;
        const rate = bps ? ` · ${(bps / 2 ** 20).toFixed(1)} MB/s · còn ~${fmtT(left / bps).replace(/\.\d$/, "")}` : "";
        $("up-txt").textContent = f < 1 ? `Đang tải lên ${Math.round(f * 100)}%${rate}` : "Đã tải lên, đang khởi động…";
      };
      prog(0);
      try {
        if (gpsFile) { $("up-txt").textContent = "Đang đọc log GPS…"; q.gps = (await api.uploadGps(gpsFile)).gps_id; }
        if (radarFile) { $("up-txt").textContent = "Đang đọc log radar…"; q.radar = (await api.uploadRadar(radarFile)).radar_id; }
        await api.upload(picked, q, prog); clearPick(); location.hash = "#live";
      }
      catch (err) { $("form-error").textContent = err.message; setStep(picked ? 2 : 1); }
      finally { $("submit").disabled = false; $("up-prog").hidden = true; }
    });
  }
  async function renderRecent() {
    const body = $("recent-body");
    let list;
    try { list = (await api.runs()).slice(0, 5); } catch (e) { body.innerHTML = `<tr><td colspan="5" class="form-error">${esc(e.message)}</td></tr>`; return; }
    body.innerHTML = list.length ? list.map((r) => `<tr><td class="mono">${when(r.started_unix)}</td><td>${esc(r.video)}</td><td class="num">${ni(r.frames)}</td><td>${stateCell(r.state)}</td>
      <td class="act">${r.video_url ? `<a class="btn small" href="#runs/${r.run_id}">Xem lại</a>` : ""}</td></tr>`).join("")
      : `<tr><td colspan="5" class="muted">Chưa có lần chạy nào.</td></tr>`;
  }

  /* =========================================================================
     Kết quả đo: như phần kết quả của comma_ai/lead_distance (pages/Upload_video.py), từ lead_distance.csv
     (một dòng mỗi tick model) và calibration.json
     ========================================================================= */
  const RES_COLORS = ["#2a78d6", "#eb6834"];   // đã lọc, thô
  const results = new Map();                   // run_id -> { rows, calib }
  const shown = { live: null, replay: null };
  // vẽ lại khi canvas có kích thước thật: lúc dữ liệu về, khung nhìn có thể còn ẩn (rộng 0)
  for (const pre of ["live", "replay"]) new ResizeObserver(() => drawResult(pre)).observe($(`${pre}-res-chart`));
  function parseCsv(text) {
    const [head, ...lines] = text.trim().split(/\r?\n/), keys = head.split(",");
    return lines.map((l) => { const v = l.split(","), o = {}; keys.forEach((k, i) => { const x = Number(v[i]); o[k] = Number.isFinite(x) ? x : null; }); return o; });
  }
  async function showResult(pre, run) {
    const panel = $(`${pre}-res`);
    if (!run) { panel.hidden = true; shown[pre] = null; return; }
    panel.hidden = false;
    if (shown[pre] === run.run_id && results.has(run.run_id)) return drawResult(pre);
    shown[pre] = run.run_id;
    $(`${pre}-res-csv`).href = run.csv_url; $(`${pre}-res-csv`).download = `${run.run_id}_lead.csv`;
    $(`${pre}-res-calib`).href = run.calibration_url; $(`${pre}-res-calib`).download = `${run.run_id}_calibration.json`;
    if (!results.has(run.run_id)) {
      try {
        const [text, calib] = await Promise.all([api.text(run.csv_url), call(run.calibration_url).catch(() => ({}))]);
        results.set(run.run_id, { rows: parseCsv(text), calib });
      } catch (e) { $(`${pre}-res-warn`).textContent = `Không tải được kết quả: ${e.message}`; return; }
    }
    if (shown[pre] !== run.run_id) return;
    const { rows, calib } = results.get(run.run_id), has = rows.filter((r) => isNum(r.lead_dist_filtered_m));
    const d = has.map((r) => r.lead_dist_bumper_m).sort((a, b) => a - b);
    $(`${pre}-res-has`).textContent = rows.length ? `${Math.round(100 * has.length / rows.length)}%` : "—";
    $(`${pre}-res-min`).textContent = d.length ? `${nf(d[0])} m` : "—";
    $(`${pre}-res-med`).textContent = d.length ? `${nf(d.length % 2 ? d[(d.length - 1) / 2] : (d[d.length / 2 - 1] + d[d.length / 2]) / 2)} m` : "—";
    const rpy = calib.rpy_deg, sg = (v) => `${v >= 0 ? "+" : ""}${nf(v, 2)}°`, bump = calib.bumper_m || 0;
    $(`${pre}-res-cal`).textContent = (rpy ? `Hiệu chỉnh tự động: pitch ${sg(rpy[1])}, yaw ${sg(rpy[2])}, roll ${sg(rpy[0])}; tiêu cự ${ni(Math.round(calib.focal_px))} px`
      + (isNum(calib.gps_offset_s) ? `; GPS lệch ${calib.gps_offset_s >= 0 ? "+" : ""}${nf(calib.gps_offset_s, 2)} s` : "") + ". " : "")
      + (bump ? "Khoảng cách tính từ đầu xe" : "Khoảng cách tính từ camera")
      + ". Thang đo theo thông số ống kính đã nhập; góc camera tự hiệu chỉnh live (ổn định sau ~2 s). Sai thông số ống kính → mọi khoảng cách sai theo cùng một tỉ lệ.";
    $(`${pre}-res-warn`).textContent = flagText(calib.flags);
    drawResult(pre);
  }
  function drawResult(pre) {
    const id = shown[pre], res = id && results.get(id); if (!res) return;
    const cv = $(`${pre}-res-chart`), dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
    if (!W || !H) return;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    const bump = res.calib.bumper_m || 0, rows = res.rows;
    const pts = rows.map((r) => ({ t: r.time_s, f: r.lead_dist_bumper_m, raw: isNum(r.lead_dist_raw_m) ? r.lead_dist_raw_m - bump : null }));
    const t1 = Math.max(1, ...pts.map((p) => p.t)), vmax = Math.max(10, ...pts.flatMap((p) => [p.f, p.raw].filter(isNum))) * 1.08;
    const PL = 40, PR = 10, T = 8, B = 22, X = (t) => PL + (W - PL - PR) * t / t1, Y = (v) => T + (H - T - B) * (1 - v / vmax);
    g.strokeStyle = COLOR.line || "#2a3a4d"; g.fillStyle = COLOR.muted || "#7f93a8"; g.lineWidth = 1; g.font = "10px ui-monospace, Consolas, monospace";
    for (let v = 0; v <= vmax; v += vmax > 120 ? 50 : 20) { g.beginPath(); g.moveTo(PL, Y(v)); g.lineTo(W - PR, Y(v)); g.stroke(); g.textAlign = "right"; g.textBaseline = "middle"; g.fillText(`${v} m`, PL - 4, Y(v)); }
    g.textAlign = "center"; g.textBaseline = "top";
    for (let t = 0; t <= t1; t += t1 > 120 ? 30 : 10) g.fillText(`${t}s`, X(t), H - B + 6);
    g.fillStyle = RES_COLORS[1]; g.globalAlpha = 0.6;
    for (const p of pts) if (isNum(p.raw)) { g.beginPath(); g.arc(X(p.t), Y(p.raw), 1.6, 0, 7); g.fill(); }
    g.globalAlpha = 1; g.strokeStyle = RES_COLORS[0]; g.lineWidth = 2; g.beginPath();
    let pen = false;
    for (const p of pts) { if (!isNum(p.f)) { pen = false; continue; } pen ? g.lineTo(X(p.t), Y(p.f)) : g.moveTo(X(p.t), Y(p.f)); pen = true; }
    g.stroke();
    const v = pre === "replay" ? $("replay-video") : $("result");
    if (v && v.src && isNum(v.currentTime)) { g.strokeStyle = "#888"; g.setLineDash([4, 3]); g.beginPath(); g.moveTo(X(v.currentTime), T); g.lineTo(X(v.currentTime), H - B); g.stroke(); g.setLineDash([]); }
    cv.onclick = (e) => { const r = cv.getBoundingClientRect(), t = (e.clientX - r.left - PL) / (W - PL - PR) * t1;
      if (v && v.src && t >= 0 && t <= t1) { v.currentTime = t; v.play().catch(() => {}); } };
  }

  /* =========================================================================
     Lịch sử và xem lại
     ========================================================================= */
  let runs = [], openId = null, wantOpen = null;
  const logs = new Map();   // run_id -> decisions.json (lần chạy đã xong không đổi nữa)
  const loadLog = async (id) => { if (!logs.has(id)) logs.set(id, await api.file(id, "decisions.json")); return logs.get(id); };
  const logPts = (log) => log.frames.map((f) => ({ t: f.t_s, gap: f.gap_m, ttc: f.ttc_s, level: f.level }));
  async function renderRuns() {
    const body = $("runs-body");
    try { runs = await api.runs(); } catch (e) { body.innerHTML = `<tr><td colspan="8" class="form-error">${esc(e.message)}</td></tr>`; return; }
    body.innerHTML = runs.length ? runs.map((r) => `<tr class="pick${r.run_id === openId ? " sel" : ""}" data-id="${r.run_id}" tabindex="0">
      <td>${esc(r.video)}<br><span class="mono small muted">${r.run_id}</span></td><td class="mono">${when(r.started_unix)}</td><td class="num">${ni(r.frames)}</td><td>${stateCell(r.state)}</td>
      ${LEVELS.map((k) => `<td class="num">${r.said ? ni(r.said[k]) : "—"}</td>`).join("")}
      <td class="act"><button class="btn small outline danger" data-del="${r.run_id}" aria-label="Xoá lần chạy ${r.run_id}"><svg><use href="#i-trash"/></svg>Xoá</button></td></tr>`).join("")
      : `<tr><td colspan="8" class="muted">Chưa có lần chạy nào.</td></tr>`;
    const target = wantOpen || openId; wantOpen = null;
    if (target && runs.some((r) => r.run_id === target)) openRun(target); else { openId = null; $("replay").hidden = true; }
  }
  async function openRun(id) {
    const r = runs.find((x) => x.run_id === id); if (!r) return;
    openId = id;
    if (route === "runs") history.replaceState(null, "", `#runs/${id}`);
    document.querySelectorAll("#runs-body tr.pick").forEach((tr) => tr.classList.toggle("sel", tr.dataset.id === id));
    $("replay").hidden = false; $("replay-name").textContent = r.video;
    const vid = $("replay-video");
    if (r.video_url) { if (!vid.src.endsWith(r.video_url)) vid.src = r.video_url; } else { vid.removeAttribute("src"); vid.load(); }
    for (const [el, url, name] of [[$("replay-video-dl"), r.video_url, `${id}.mp4`], [$("replay-log-dl"), r.log_url, `${id}-decisions.json`]]) {
      el.hidden = !url; if (url) { el.href = url; el.download = name; }
    }
    showResult("replay", r.csv_url ? r : null);
    const evBox = $("replay-events");
    if (!r.log_url) { evBox.innerHTML = `<li class="none muted">${r.state === "failed" ? "Lần chạy lỗi, không có log." : "Lần chạy chưa xong."}</li>`; replay.pts = []; replay.frames = []; drawReplay(); return; }
    evBox.innerHTML = `<li class="none muted">Đang tải log…</li>`;
    let log;
    try { log = await loadLog(id); } catch (e) { evBox.innerHTML = `<li class="none form-error">${esc(e.message)}</li>`; return; }
    if (openId !== id) return;
    replay.pts = logPts(log); replay.events = log.events; replay.frames = log.frames; replay.len = log.frames.length ? log.frames[log.frames.length - 1].t_s : 0;
    scenes.replay.redraw();
    evBox.innerHTML = log.events.length ? log.events.map((e) => `<li class="seek" data-t="${e.t_s}" tabindex="0"><span class="k">${fmtT(e.t_s)}</span><span><span class="tag ${e.kind}">${LEVEL_VI[e.kind]}</span> “${esc(e.text)}”<br><span class="r">${esc(e.reason)}</span></span></li>`).join("")
      : `<li class="none muted">Lần chạy này không nói câu nào.</li>`;
    drawReplay();
  }
  const replay = { pts: [], events: [], frames: [], len: 0 };
  function drawReplay() {
    const v = $("replay-video");
    drawChart($("replay-chart"), replay.pts, { t0: 0, t1: Math.max(1, replay.len), levels: true, events: replay.events, head: openId && v.src ? v.currentTime : null });
  }
  function seek(t) { const v = $("replay-video"); if (v.src) { v.currentTime = t; v.play().catch(() => {}); } }
  function wireRuns() {
    $("runs-refresh").addEventListener("click", renderRuns);
    $("runs-body").addEventListener("click", async (e) => {
      const del = e.target.closest("[data-del]");
      if (del) {
        e.stopPropagation();
        if (!confirm("Xoá lần chạy này cùng video đã tải lên? Không khôi phục được.")) return;
        $("runs-error").textContent = "";
        try { await api.del(del.dataset.del); logs.delete(del.dataset.del); if (openId === del.dataset.del) openId = null; renderRuns(); }
        catch (err) { $("runs-error").textContent = err.message; }
        return;
      }
      const tr = e.target.closest("tr.pick"); if (tr) openRun(tr.dataset.id);
    });
    $("runs-body").addEventListener("keydown", (e) => { const tr = e.target.closest("tr.pick"); if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openRun(tr.dataset.id); } });
    $("replay-events").addEventListener("click", (e) => { const li = e.target.closest("li[data-t]"); if (li) seek(Number(li.dataset.t)); });
    $("replay-events").addEventListener("keydown", (e) => { const li = e.target.closest("li[data-t]"); if (li && e.key === "Enter") seek(Number(li.dataset.t)); });
    $("replay-chart").addEventListener("click", (e) => { const t = chartT($("replay-chart"), e.clientX); if (t !== null) seek(t); });
    let pending = false;
    $("replay-video").addEventListener("timeupdate", () => { scenes.replay.redraw(); if (!pending) { pending = true; requestAnimationFrame(() => { pending = false; drawReplay(); drawResult("replay"); }); } });
    $("result").addEventListener("timeupdate", () => drawResult("live"));
  }

  /* =========================================================================
     Lab: BT-A trên segment comma2k19 so với radar và log tốc độ CAN của xe (như app.py của comma_ai/lead_distance).
     Kết quả lưu trên server; ngưỡng chọn xe cùng làn tính lại ở đây bằng leadMask (bản JS của lead_mask).
     ========================================================================= */
  const LAB_COLORS = { model: "#2a78d6", kalman: "#2bb673", radar: "#eb6834" };
  const LAB_BANDS = [[0, 20], [20, 40], [40, 60], [60, 200]];
  const lab = { segs: [], id: null, res: null, dist: null, poll: null, live: false, grab: 0 };
  const LAB_COLS = ["t_s", "lead_x_m", "lead_y_m", "lead_prob", "lead_std_m", "gap_kalman_m", "ego_model_mps", "ego_log_mps", "radar_m", "curv_gt", "curv_yaw", "curv_drawn"];
  function leadMask(x, y, p, minProb, maxLat, warmup = 20, exitRatio = 0.5, hold = 8) {
    const out = new Array(x.length).fill(false); let on = false, miss = 0;
    for (let i = 0; i < x.length; i++) {
      const ok = isNum(x[i]) && isNum(y[i]) && isNum(p[i]) && x[i] > 0 && i >= warmup;
      const enter = ok && p[i] >= minProb && Math.abs(y[i]) <= maxLat;
      const stay = ok && p[i] >= minProb * exitRatio && Math.abs(y[i]) <= maxLat * 1.25;
      if (enter || (on && stay)) { on = true; miss = 0; } else if (on) { miss += 1; on = miss <= hold; }
      out[i] = on;
    }
    return out;
  }
  async function renderLab(want) {
    try { lab.segs = await api.labSegments(); } catch (e) { $("lab-error").textContent = e.message; return; }
    const sel = $("lab-seg"), keep = want || sel.value || lab.id;
    sel.innerHTML = lab.segs.length ? lab.segs.map((g) => `<option value="${esc(g.id)}">${esc(g.id)} · ${g.has_radar ? "radar" : "không radar"} · ${g.has_speed ? "log tốc độ" : "không log"}${g.cached ? " · đã chạy" : ""}</option>`).join("")
      : `<option value="">Không có segment</option>`;
    $("lab-seg-s").textContent = lab.segs.length ? `${lab.segs.length} segment trong RW_LAB_DIR` : "Chưa có bài kiểm tra: đặt dữ liệu vào RW_LAB_DIR";
    if (lab.segs.some((g) => g.id === keep)) sel.value = keep;
    $("lab-run").disabled = !lab.segs.length;
    labWatch();
    loadLab(sel.value);
  }
  async function loadLab(id) {
    if (lab.live) { $("lab-seg").value = lab.id; return; }   // đang chạy trực tiếp: giữ segment đang chạy
    lab.id = id; lab.res = null; $("lab-error").textContent = "";
    const g = lab.segs.find((x) => x.id === id), v = $("lab-video");
    if (route === "lab" && id) history.replaceState(null, "", `#lab/${id}`);
    $("lab-tag").textContent = id ? `Segment ${id}` : "—";
    if (!g || !g.cached) { v.hidden = true; v.removeAttribute("src"); $("lab-empty").hidden = false; labCompute(); return; }
    let res;
    try { res = await api.labResult(id); } catch (e) { $("lab-error").textContent = e.message; return; }
    if (lab.id !== id) return;
    lab.res = res;
    $("lab-bump").value = res.bumper_m; $("lab-fy").value = res.fy_px; $("lab-log").checked = res.use_log; $("lab-wide").value = res.wide || "dup";
    const url = `/api/lab/segments/${encodeURIComponent(id)}/video?v=${Math.round(res.created_unix)}`;
    if (!v.src.endsWith(url)) v.src = url;
    v.hidden = false; $("lab-empty").hidden = true;
    labCompute();
  }
  function labErrors(est, ref) {
    const rows = [];
    for (const [lo, hi] of [[0, 1e9], ...LAB_BANDS]) {
      const e = [], rel = [];
      est.forEach((d, i) => { const r = ref[i]; if (isNum(d) && isNum(r) && r >= lo && r < hi) { e.push(d - r); rel.push(Math.abs(d - r) / r); } });
      const a = e.map(Math.abs).sort((p, q) => p - q), mean = (xs) => xs.reduce((s, x) => s + x, 0) / xs.length;
      rows.push({ band: hi > 1e8 ? "Tất cả" : `${lo}–${hi === 200 ? "200" : hi} m`, n: e.length,
        mae: e.length ? mean(a) : null, med: e.length ? a[Math.floor((a.length - 1) / 2)] : null, bias: e.length ? mean(e) : null, rel: e.length ? mean(rel) : null });
    }
    return rows;
  }
  function labCompute() {
    const r = lab.res, body = $("lab-err");
    $("lab-prob-v").textContent = nf(Number($("lab-prob").value), 2); $("lab-lat-v").textContent = `${nf(Number($("lab-lat").value), 1)} m`;
    if (!r) { lab.dist = null; body.innerHTML = `<tr><td colspan="7" class="muted">Chưa có kết quả cho segment này.</td></tr>`; $("lab-cap").textContent = ""; $("lab-speed-cap").textContent = ""; $("lab-csv").hidden = true; labDraw(); labMetrics(); return; }
    const mask = leadMask(r.lead_x_m, r.lead_y_m, r.lead_prob, Number($("lab-prob").value), Number($("lab-lat").value));
    lab.dist = r.lead_x_m.map((x, i) => mask[i] && isNum(x) ? x - r.bumper_m : null);
    const model = labErrors(lab.dist, r.radar_m), kal = labErrors(r.gap_kalman_m, r.radar_m);
    body.innerHTML = model.map((m, k) => [[m, "Model", LAB_COLORS.model], [kal[k], "Kalman", LAB_COLORS.kalman]].map(([e, name, col], j) =>
      `<tr>${j ? "" : `<td rowspan="2">${e.band}</td>`}<td><i class="sw" style="background:${col}"></i>${name}</td><td class="num">${ni(e.n)}</td><td class="num">${isNum(e.mae) ? `${nf(e.mae)} m` : "—"}</td>
       <td class="num">${isNum(e.med) ? `${nf(e.med)} m` : "—"}</td><td class="num">${isNum(e.bias) ? `${e.bias >= 0 ? "+" : ""}${nf(e.bias)} m` : "—"}</td><td class="num">${isNum(e.rel) ? `${nf(100 * e.rel)}%` : "—"}</td></tr>`).join("")).join("");
    const has = mask.filter(Boolean).length, rad = r.radar_m.filter(isNum).length;
    $("lab-cap").textContent = `Có xe cùng làn ở ${ni(has)}/${ni(r.frames)} frame; radar có tham chiếu ở ${ni(rad)} frame. Tính từ đầu xe (đã trừ ${nf(r.bumper_m, 2)} m); tiêu cự ${ni(r.fy_px)} px${lab.live ? " (đang chạy trực tiếp: số liệu cập nhật theo từng frame)." : `; góc ước lượng trên 300 frame đầu pitch ${nf(r.rpy_deg[1], 2)}°, yaw ${nf(r.rpy_deg[2], 2)}°, roll ${nf(r.rpy_deg[0], 2)}°${r.rpy_applied_deg ? `, áp dụng yaw ${nf(r.rpy_applied_deg[2], 2)}°` : ""}; đầu vào camera rộng ${r.wide || "dup"}.`} Radar chỉ là tham chiếu gần đúng: track gần nhất trong ±1,6 m ngang, có thể bắt nhầm xe ở xa.`;
    const sp = r.ego_model_mps.map((v, i) => isNum(v) && isNum(r.ego_log_mps[i]) ? v - r.ego_log_mps[i] : null).filter(isNum);
    $("lab-speed-cap").textContent = sp.length ? `Model so với tốc độ thực tế (log) trên ${ni(sp.length)} frame: lệch trung bình ${nf(sp.reduce((s, x) => s + x, 0) / sp.length * 3.6)} km/h, MAE ${nf(sp.reduce((s, x) => s + Math.abs(x), 0) / sp.length * 3.6)} km/h. Tỉ lệ tốc độ model/log lệch khỏi 1 nghĩa là tiêu cự sai cùng tỉ lệ đó.${r.use_log ? " Lần chạy này dùng log tốc độ thực tế làm tốc độ xe mình (HUD, ngưỡng cảnh báo, TTC)." : ""}` : "Segment không có log tốc độ.";
    const csv = ["frame,time_s,lead_dist_m,lead_dist_std_m,lead_dist_kalman_m,lead_lat_m,lead_prob,ego_speed_model_mps,ego_speed_log_mps,radar_ref_m",
      ...r.t_s.map((t, i) => [i, t, lab.dist[i], mask[i] ? r.lead_std_m[i] : null, r.gap_kalman_m[i], r.lead_y_m[i], r.lead_prob[i], r.ego_model_mps[i], r.ego_log_mps[i], r.radar_m[i]]
        .map((v) => isNum(v) ? String(Math.round(v * 1000) / 1000) : "").join(","))].join("\n");
    const a = $("lab-csv"); if (a.href.startsWith("blob:")) URL.revokeObjectURL(a.href);
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); a.download = `${r.segment}_lead_distance.csv`; a.hidden = false;
    labDraw(); labMetrics();
  }
  function labIndex() { const r = lab.res, v = $("lab-video"); if (r && lab.live) return Math.max(0, r.frames - 1); return r ? Math.max(0, Math.min(r.frames - 1, Math.round((v.currentTime || 0) * r.fps))) : 0; }
  function labMetrics() {   // hai dòng: khoảng cách model | radar | Δ, tốc độ model | log thực tế | Δ; thiếu số nào thì "_"
    const r = lab.res, i = labIndex(), none = "_", sg = (v) => v >= 0 ? "+" : "";
    const d = r && lab.dist ? lab.dist[i] : null, rad = r ? r.radar_m[i] : null;
    const est = r ? r.ego_model_mps[i] : null, real = r ? r.ego_log_mps[i] : null;
    $("lab-m-dist").textContent = isNum(d) ? `${nf(d)} m` : none;
    $("lab-m-std").textContent = isNum(d) && isNum(r.lead_std_m[i]) ? `± ${nf(r.lead_std_m[i])} m · Kalman ${isNum(r.gap_kalman_m[i]) ? `${nf(r.gap_kalman_m[i])} m` : none}` : "";
    $("lab-m-radar").textContent = isNum(rad) ? `${nf(rad)} m` : none;
    $("lab-m-diff").textContent = isNum(d) && isNum(rad) ? `${sg(d - rad)}${nf(d - rad)} m` : none;
    $("lab-m-ego").textContent = isNum(est) ? `${nf(est * 3.6, 0)} km/h` : none;
    $("lab-m-log").textContent = isNum(real) ? `${nf(real * 3.6, 0)} km/h` : none;
    $("lab-m-sd").textContent = isNum(est) && isNum(real) ? `${sg(est - real)}${nf((est - real) * 3.6, 0)} km/h` : none;
  }
  function lineChart(cv, t, series, unit, head, signed = false) {
    const dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
    if (!W || !H) return;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    if (!t || !t.length) return;
    const vals = series.flatMap((s) => s.v.filter(isNum));
    const t1 = Math.max(1, t[t.length - 1]), vmax = Math.max(signed ? 4 : 10, ...(signed ? vals.map(Math.abs) : vals)) * 1.08, vmin = signed ? -vmax : 0;
    const PL = 46, PR = 10, PT = 8, PB = 22, X = (x) => PL + (W - PL - PR) * x / t1, Y = (v) => PT + (H - PT - PB) * (1 - (v - vmin) / (vmax - vmin));
    const step = signed ? Math.max(1, Math.round(vmax / 3)) : vmax > 150 ? 50 : vmax > 60 ? 20 : 10;
    g.strokeStyle = COLOR.line || "#2a3a4d"; g.fillStyle = COLOR.muted || "#7f93a8"; g.lineWidth = 1; g.font = "10px ui-monospace, Consolas, monospace";
    for (let v = signed ? -Math.floor(vmax / step) * step : 0; v <= vmax; v += step) { g.beginPath(); g.moveTo(PL, Y(v)); g.lineTo(W - PR, Y(v)); g.stroke(); g.textAlign = "right"; g.textBaseline = "middle"; g.fillText(`${v} ${unit}`, PL - 4, Y(v)); }
    g.textAlign = "center"; g.textBaseline = "top";
    for (let s = 0; s <= t1; s += t1 > 120 ? 30 : 10) g.fillText(`${s}s`, X(s), H - PB + 6);
    for (const s of series) {
      g.strokeStyle = g.fillStyle = s.color; g.lineWidth = s.width || 2; g.globalAlpha = s.alpha || 1; g.beginPath();
      let pen = false;
      s.v.forEach((v, i) => { if (!isNum(v)) { pen = false; return; } pen ? g.lineTo(X(t[i]), Y(v)) : g.moveTo(X(t[i]), Y(v)); pen = true; });
      g.stroke(); g.globalAlpha = 1;
    }
    if (isNum(head)) { g.strokeStyle = "#888"; g.lineWidth = 1; g.setLineDash([4, 3]); g.beginPath(); g.moveTo(X(head), PT); g.lineTo(X(head), H - PB); g.stroke(); g.setLineDash([]); }
    cv.onclick = (e) => { const b = cv.getBoundingClientRect(), x = (e.clientX - b.left - PL) / (W - PL - PR) * t1, v = $("lab-video");
      if (v.src && x >= 0 && x <= t1) { v.currentTime = x; v.play().catch(() => {}); } };
  }
  function labDraw() {
    const r = lab.res, head = r && lab.live ? null : r && $("lab-video").src ? $("lab-video").currentTime : null;
    lineChart($("lab-chart-dist"), r && r.t_s, r ? [
      ...($("lab-show-radar").checked ? [{ v: r.radar_m, color: LAB_COLORS.radar, width: 2 }] : []),
      { v: r.gap_kalman_m, color: LAB_COLORS.kalman, width: 1.5, alpha: 0.9 },
      { v: lab.dist, color: LAB_COLORS.model, width: 2 }] : [], "m", head);
    lineChart($("lab-chart-speed"), r && r.t_s, r ? [{ v: r.ego_log_mps.map((v) => isNum(v) ? v * 3.6 : null), color: LAB_COLORS.radar },
      { v: r.ego_model_mps.map((v) => isNum(v) ? v * 3.6 : null), color: LAB_COLORS.model }] : [], "km/h", head);
    const has = r && (r.curv_yaw || []).some(isNum);   // cũ hơn bản có độ cong: không có cột, ẩn khối
    $("lab-curv-panel").hidden = !has;
    if (!has) return;
    lineChart($("lab-chart-curv"), r.t_s, [
      { v: r.curv_gt, color: LAB_COLORS.radar, width: 2.5 },
      { v: r.curv_yaw, color: LAB_COLORS.kalman, width: 1.5, alpha: 0.9 },
      { v: r.curv_drawn, color: LAB_COLORS.model, width: 2 }], "1/km", head, true);
    const err = (a) => { const e = a.map((v, i) => isNum(v) && isNum(r.curv_gt[i]) && Math.abs(r.curv_gt[i]) > 1 ? Math.abs(v - r.curv_gt[i]) : null).filter(isNum);
      return e.length ? e.reduce((s, v) => s + v, 0) / e.length : null; };
    const ey = err(r.curv_yaw), ed = err(r.curv_drawn);
    $("lab-curv-cap").textContent = r.curv_gt.some(isNum)
      ? `Sai số TB trên đoạn cong (|thật| > 1/km): yaw ${isNum(ey) ? nf(ey, 2) : "—"} · đường đang vẽ ${isNum(ed) ? nf(ed, 2) : "—"} (1/km; 1/km = bán kính 1000 m).`
      : "Segment này chưa có độ cong thật (gt.csv): chỉ so yaw với đường đang vẽ.";
  }
  function labLiveStart(segment) {   // đang chạy: ảnh /api/lab/frame và số liệu /api/lab/live thay cho video và kết quả đã lưu
    lab.live = true; lab.id = segment; $("lab-seg").value = segment; $("lab-error").textContent = "";
    lab.res = { segment, frames: 0, fps: 20, bumper_m: Number($("lab-bump").value), fy_px: Number($("lab-fy").value), use_log: $("lab-log").checked, wide: $("lab-wide").value, rpy_deg: [0, 0, 0], created_unix: 0 };
    for (const k of LAB_COLS) lab.res[k] = [];
    const v = $("lab-video"), img = $("lab-live"); v.pause(); v.hidden = true; img.hidden = false; $("lab-empty").hidden = true; $("lab-tag").textContent = `Trực tiếp · ${segment}`;
    const token = lab.grab = Date.now(), next = (ms) => { if (lab.grab === token) setTimeout(grab, ms); };
    let shown = null;
    async function grab() {   // như ảnh trực tiếp ở Lái thử: ảnh sau chỉ xin khi ảnh trước đã hiện
      try {
        const r = await fetch(`/api/lab/frame?t=${Date.now()}`, { cache: "no-store" });
        if (r.status !== 200) return next(300);
        const url = URL.createObjectURL(await r.blob()), pre = new Image(); pre.src = url; await pre.decode();
        if (lab.grab !== token) { URL.revokeObjectURL(url); return; }
        img.src = url; if (shown) URL.revokeObjectURL(shown); shown = url; next(50);
      } catch { next(300); }
    }
    grab(); labCompute();
  }
  function labLiveStop() { lab.live = false; lab.grab = 0; $("lab-live").hidden = true; $("lab-live").removeAttribute("src"); }
  async function labLiveData() {
    const r = lab.res; if (!lab.live || !r) return;
    try {
      const d = await api.labLive(r.frames);
      if (!lab.live || d.segment !== r.segment || d.start !== r.frames) return;
      for (const k of LAB_COLS) r[k].push(...d[k]);
      r.frames = d.frames; r.fps = d.fps;
      if (d.frames) labCompute();
    } catch { /* lần sau thử lại */ }
  }
  async function labWatch() {   // tiến độ lần chạy Lab (một lần một segment, chạy nền trên server)
    clearTimeout(lab.poll);
    let st;
    try { st = await api.labStatus(); } catch { lab.poll = setTimeout(labWatch, 2000); return; }
    const running = st.state === "running";
    $("lab-state").querySelector(".dot").className = "dot " + ({ running: "run", done: "ok", failed: "bad", stopped: "warn" }[st.state] || "");
    $("lab-state").lastElementChild.textContent = running ? `Đang chạy segment ${st.segment}` : st.state === "failed" ? "Lỗi" : st.state === "done" ? `Xong segment ${st.segment}` : st.state === "stopped" ? `Đã dừng segment ${st.segment}` : "Sẵn sàng";
    $("lab-prog").hidden = !running; $("lab-run").disabled = running || !lab.segs.length; $("lab-stop").hidden = !running;
    if (running && !lab.live) labLiveStart(st.segment);
    if (running) await labLiveData();
    if (!running && lab.live) { labLiveStop(); if (st.state !== "done") loadLab(lab.id); }
    if (running) { const f = st.total ? st.done / st.total : 0; $("lab-bar").style.width = `${f * 100}%`; const c = st.calib_frames || 0;
      const calibrating = st.done <= c && c, q = st.calib_rpy_deg, sg = (v) => `${v >= 0 ? "+" : ""}${nf(v, 2)}°`;
      $("lab-tag").textContent = calibrating ? `Hiệu chỉnh góc camera · ${st.segment}` : `Trực tiếp · ${st.segment}`;
      $("lab-txt").textContent = calibrating
        ? `Segment ${st.segment}: hiệu chỉnh góc camera, frame ${ni(st.done)}/${ni(c)}` + (q ? ` · yaw ${sg(q[2])} (sẽ áp) · pitch ${sg(q[1])} · roll ${sg(q[0])}${st.calib_settled ? " · đã ổn định" : " · đang thu thập mẫu"}` : "")
        : `Segment ${st.segment}: frame ${ni(st.done - c)}/${ni(st.total - c)}`; }
    if (st.state === "failed" && st.error) $("lab-error").textContent = st.error;
    if (lab.wasRunning && !running && st.state === "done") { lab.wasRunning = false; renderLab(st.segment); return; }
    lab.wasRunning = running;
    if (running && route === "lab") lab.poll = setTimeout(labWatch, 500);
  }
  function wireLab() {
    $("lab-seg").addEventListener("change", (e) => loadLab(e.target.value));
    for (const id of ["lab-prob", "lab-lat"]) $(id).addEventListener("input", labCompute);
    $("lab-show-radar").addEventListener("change", labDraw);
    $("lab-run").addEventListener("click", async () => {
      const id = $("lab-seg").value; if (!id) return;
      $("lab-error").textContent = "";
      try { await api.labRun(id, { bumper: Number($("lab-bump").value), fy: Number($("lab-fy").value), log: $("lab-log").checked, wide: $("lab-wide").value }); lab.wasRunning = true; labWatch(); }
      catch (e) { $("lab-error").textContent = e.message; }
    });
    $("lab-stop").addEventListener("click", async () => {   // dừng ngay, kể cả lúc đang hiệu chỉnh góc camera; kết quả đã lưu trước đó giữ nguyên
      $("lab-stop").disabled = true;
      try { await api.labStop(); labWatch(); } catch (e) { $("lab-error").textContent = e.message; } finally { $("lab-stop").disabled = false; }
    });
    $("lab-video").addEventListener("timeupdate", () => { labMetrics(); labDraw(); });
    $("lab-video").addEventListener("seeked", () => { labMetrics(); labDraw(); });
    for (const id of ["lab-chart-dist", "lab-chart-speed"]) new ResizeObserver(labDraw).observe($(id));
  }

  /* =========================================================================
     Bản đồ 3D quanh xe (scene3d.js): Lái thử lấy từ bản tin trực tiếp, xem lại lấy khung của decisions.json theo giờ video
     ========================================================================= */
  const scenes = {
    live: RWScene3D.create($("live-3d"), () => {
      const m = L.measure, d = L.decision;
      if (!m) return { note: L.state === "loading" ? "Đang nạp model…" : "Chưa có dữ liệu: chạy một video" };
      return { ego_kmh: m.ego_kmh, gap_m: m.lead.gap_m, thr_m: d ? d.threshold_m : null, ttc_s: m.ttc_s, level: d ? d.level : null };
    }),
    replay: RWScene3D.create($("replay-3d"), () => {
      const fr = replay.frames; if (!fr || !fr.length) return { note: "Chọn một lần chạy đã xong" };
      const f = fr[bisect(fr, $("replay-video").currentTime || 0)];
      return { ego_kmh: f.ego_mps * 3.6, gap_m: f.gap_m, thr_m: null, ttc_s: f.ttc_s, level: f.level };
    }),
  };
  // trang giới thiệu: cảnh minh hoạ (số liệu dựng sẵn, không phải số đo), xe mình chạy 90 km/h trên đường 3 làn.
  // Xe phía trước lúc gần lúc xa (20–32 m); làn trái chậm hơn nên bị vượt dần; làn phải nhanh hơn, vượt lên rồi
  // chuyển vào làn mình ở phía trước xe dẫn đầu; mọi xe hơi lắc ngang trong làn
  RWScene3D.create($("hero-3d"), () => {
    const t = performance.now() / 1000, lap = (z0, v) => ((z0 + v * t) % 240 + 240) % 240 - 40;
    const sway = (k) => 0.05 * Math.sin(t * 0.9 + k * 2.1);
    const merge = (z) => { const u = Math.min(1, Math.max(0, (z - 50) / 25)); return 1 - u * u * (3 - 2 * u); };
    const left = [lap(30, -6), lap(150, -6)].map((z, i) => ({ lane: -1 + sway(i), z }));
    const right = [lap(0, 5), lap(120, 5)].map((z, i) => ({ lane: merge(z) + sway(i + 2), z }));
    return { ego_kmh: 90, gap_m: 26 + 6 * Math.sin(t * 0.35), traffic: [...left, ...right] };
  }, { interactive: false, hud: false, theme: "daylight", view: { yaw: -0.42, pitch: 0.58, dist: 36 } });
  document.querySelectorAll(".views").forEach((grp) => grp.addEventListener("click", (e) => {
    const b = e.target.closest("[data-cam]"); if (!b) return;
    grp.querySelectorAll("[data-cam]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    scenes[grp.dataset.scene === "live-3d" ? "live" : "replay"].view(b.dataset.cam);
  }));

  /* =========================================================================
     Khởi động
     ========================================================================= */
  readColors();
  document.documentElement.style.setProperty("--navh", `${document.querySelector(".nav").offsetHeight}px`);
  $("scroll-cue").addEventListener("click", (e) => { e.preventDefault(); $("intro-more").scrollIntoView({ behavior: "smooth" }); });
  $("sound").addEventListener("click", (e) => { sound = !sound; const t = `Âm thanh: ${sound ? "bật" : "tắt"}`; e.currentTarget.title = t; e.currentTarget.setAttribute("aria-label", t); e.currentTarget.setAttribute("aria-pressed", String(sound)); });
  $("stop").addEventListener("click", () => api.stop().catch((err) => alert(err.message)));
  wireUpload(); wireRuns(); wireLab();
  addEventListener("resize", () => { if (route === "live") renderLive(); if (route === "runs") { drawReplay(); drawResult("replay"); } });
  addEventListener("hashchange", go);
  cfgReady.then(() => { if (route === "live") renderLive(); });
  health(); setInterval(health, 5000);
  connect();
  go();
})();
