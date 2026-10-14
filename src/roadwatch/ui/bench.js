/* Thử khả thi chạy gr14VinAI trong trình duyệt điện thoại bằng onnxruntime-web (models/ort-web, không có trong git).
   Đầu vào là mẫu số học cố định, giống hệt mẫu đã dùng để tạo reference.json bằng ONNX Runtime CPU trên laptop:
   phần tử thứ i của new_img = (7·i + 13) mod 256, của state_img_q = (3·i + 5) mod 256. Kết quả (thời gian mỗi lần,
   sai khác đầu ra) hiện trên trang và gửi về /api/bench/result để có trong log của laptop. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const models = {}; let reference = null, wasmBinary = null;   // bytes đã tải, giữ lại giữa các lần chạy
  const WASM = "/ortweb/ort-wasm-simd-threaded.asyncify.wasm";   // bản WebAssembly mà ort.webgpu.min.js dùng

  function state(text, dot) { $("b-state").lastElementChild.textContent = text; $("b-state").firstElementChild.className = "dot " + (dot || ""); }
  function line(text) { const li = document.createElement("li"); li.textContent = text; $("b-out").append(li); return li; }

  /* Tải file lớn (model 40–79 MB, WebAssembly 27 MB) qua 4G + Funnel: tải một lần hay bị đứt giữa chừng ("Load failed"),
     và mạng của laptop có lúc mất gần 1 phút (13/10/2026: DHCP xin lại địa chỉ). Tải từng đoạn CHUNK bằng HTTP Range;
     đoạn hỏng thì thử lại cho tới khi STALL_MS không có tiến triển; mỗi đoạn tải xong được lưu vào Cache Storage, nên bấm
     chạy lại sẽ tải tiếp phần còn thiếu; đủ cả file thì lưu một bản liền và xoá các đoạn. */
  const CHUNK = 2 << 20, STALL_MS = 180000, CACHE = "roadwatch-ortweb-v4";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const mb = (n) => (n / 1e6).toFixed(1);
  async function fetchBytes(url, label) {
    const li = line(`Tải ${label}…`);
    let cache = null;
    try {
      cache = await caches.open(CACHE);
      const hit = await cache.match(url);
      if (hit) { const b = new Uint8Array(await hit.arrayBuffer()); li.textContent = `${label}: dùng bản đã lưu (${mb(b.length)} MB)`; return b; }
    } catch { cache = null; }   // không có Cache Storage: vẫn tải, chỉ không lưu
    const part = (start) => `${url}?part=${start}`;
    const parts = []; let got = 0, total = null, resumed = 0;
    while (total === null || got < total) {
      let buf = null;
      if (cache && total !== null) {   // đoạn đã tải ở lần trước
        const hit = await cache.match(part(got)).catch(() => null);
        if (hit) { buf = new Uint8Array(await hit.arrayBuffer()); resumed += buf.length; }
      }
      const since = performance.now(); let tries = 0;
      while (!buf) {
        try {
          const r = await fetch(url, { headers: { Range: `bytes=${got}-${got + CHUNK - 1}` }, cache: "no-store" });
          if (r.status === 401) location.assign("/login?next=/bench");
          if (r.status !== 206 && r.status !== 200) throw new Error(`lỗi ${r.status}`);
          const b = new Uint8Array(await r.arrayBuffer());
          if (r.status === 200) { parts.length = 0; got = 0; total = b.length; }   // server không chia đoạn: đã có cả file
          else total = Number((r.headers.get("content-range") || "").split("/")[1]) || got + b.length;
          buf = b;
          if (cache && r.status === 206) await cache.put(part(got), new Response(b)).catch(() => {});
        } catch (e) {
          tries++;
          const waited = performance.now() - since;
          if (waited > STALL_MS) throw new Error(`Không tải được ${label}: mất kết nối hơn ${STALL_MS / 60000} phút (${e.message || e}). Bấm Chạy thử để tải tiếp phần còn thiếu`);
          li.textContent = `Tải ${label}: ${mb(got)}${total ? ` / ${mb(total)}` : ""} MB · mất kết nối ${Math.round(waited / 1000)} s, đang thử lại (lần ${tries})…`;
          await sleep(Math.min(5000, 1000 * tries));
        }
      }
      parts.push(buf); got += buf.length;
      li.textContent = `Tải ${label}: ${mb(got)} / ${mb(total)} MB${resumed ? ` (${mb(resumed)} MB từ lần trước)` : ""}`;
    }
    const out = new Uint8Array(got); let o = 0; for (const p of parts) { out.set(p, o); o += p.length; }
    if (cache) {
      try {
        await cache.put(url, new Response(out, { headers: { "Content-Type": "application/octet-stream" } }));
        for (let st = 0; st < got; st += CHUNK) await cache.delete(part(st));
        li.textContent += " · đã lưu";
      } catch { /* hết chỗ: lần sau tải lại */ }
    }
    return out;
  }

  function pattern(dims, a, b) {
    const n = dims.reduce((x, y) => x * y, 1), data = new Uint8Array(n);
    for (let i = 0; i < n; i++) data[i] = (i * a + b) % 256;
    return new ort.Tensor("uint8", data, dims);
  }
  /* Model có nhánh policy (như laptop): desire = 0, traffic_convention = [1, 0], hàng đợi state_desire_q, state_feat_q. */
  function policyFeeds(names) {
    const f = {}, zeros = (dims) => new ort.Tensor("float32", new Float32Array(dims.reduce((a, b) => a * b, 1)), dims);
    if (names.includes("desire")) f.desire = zeros([8]);
    if (names.includes("traffic_convention")) f.traffic_convention = new ort.Tensor("float32", new Float32Array([1, 0]), [1, 2]);
    if (names.includes("state_desire_q")) f.state_desire_q = zeros([100, 1, 8]);
    if (names.includes("state_feat_q")) f.state_feat_q = zeros([96, 1, 512]);
    return f;
  }
  function feedBack(feeds, out) { for (const k of Object.keys(feeds)) if (out["next_" + k]) feeds[k] = out["next_" + k]; }
  const HEADS = [["pose", 0, 12], ["road_transform", 12, 24], ["lane_lines", 24, 552], ["lane_lines_prob", 552, 560],
                 ["lead", 560, 704], ["lead_prob", 704, 707]];   // output_slices của gr14VinAI
  const pct = (xs, p) => { const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(p / 100 * s.length))]; };

  async function gpuInfo() {
    if (!navigator.gpu) return { webgpu: false };
    try {
      const a = await navigator.gpu.requestAdapter();
      if (!a) return { webgpu: false, why: "không có adapter" };
      const info = a.info || {};
      return { webgpu: true, vendor: info.vendor || "", architecture: info.architecture || "", shader_f16: a.features.has("shader-f16") };
    } catch (e) { return { webgpu: false, why: String(e) }; }
  }

  async function run() {
    $("b-err").textContent = ""; $("b-out").replaceChildren(); $("b-run").disabled = true;
    const ep = $("b-ep").value, model = $("b-model").value, n = Math.max(5, Math.min(5000, Number($("b-n").value) || 50));
    const result = { ep, model, n, ua: navigator.userAgent };
    try {
      if (typeof ort === "undefined") throw new Error("Chưa có onnxruntime-web trên laptop (models/ort-web)");
      state("Đang chuẩn bị…", "run");
      Object.assign(result, await gpuInfo());
      line(`WebGPU: ${result.webgpu ? `có (${result.vendor} ${result.architecture}, shader-f16 ${result.shader_f16 ? "có" : "không"})` : `không có${result.why ? ": " + result.why : ""}`}`);
      if (ep === "webgpu" && !result.webgpu) throw new Error("Trình duyệt này chưa bật WebGPU (cần Safari trên iOS 26 trở lên)");
      ort.env.wasm.wasmPaths = "/ortweb/";
      ort.env.wasm.numThreads = 1;   // nhiều luồng cần cross-origin isolation; WebGPU không cần
      ort.env.wasm.proxy = false;
      if (!reference) reference = await (await fetch("/ortweb/reference.json")).json().catch(() => null);
      if (ep === "webgpu" && !result.shader_f16 && model === "gr14VinAI.onnx")
        throw new Error("GPU này không có f16: chọn bản model FP32");
      if (!models[model]) models[model] = await fetchBytes(`/ortweb/${model}`, "model");
      // Tự tải WebAssembly rồi đưa thẳng cho thư viện: trên Safari, thư viện tự tải thì lỗi
      // "both async and sync fetching of the wasm failed" (13/10/2026), dù model tải bằng cách này được.
      if (!wasmBinary) wasmBinary = await fetchBytes(WASM, "thư viện WebAssembly");
      ort.env.wasm.wasmBinary = wasmBinary;
      state("Đang tạo phiên…", "run");
      let t = performance.now();
      const sess = await ort.InferenceSession.create(models[model], { executionProviders: [ep], graphOptimizationLevel: "all" });
      result.create_ms = Math.round(performance.now() - t);
      line(`Tạo phiên (biên dịch model): ${result.create_ms} ms`);
      const feeds = {};
      Object.assign(feeds, policyFeeds(sess.inputNames));
      for (const name of ["new_img", "state_img_q"]) {
        const dims = name === "new_img" ? [2, 6, 128, 256] : [2, 5, 6, 128, 256];
        feeds[name] = name === "new_img" ? pattern(dims, 7, 13) : pattern(dims, 3, 5);
      }
      state("Đang chạy…", "run");
      t = performance.now();
      let out = await sess.run(feeds);
      result.first_ms = Math.round(performance.now() - t);
      line(`Lần chạy đầu: ${result.first_ms} ms`);
      for (let i = 0; i < 3; i++) await sess.run(feeds);   // làm nóng
      const times = [], li = line(`Đo ${n} lần…`);
      for (let i = 0; i < n; i++) {
        t = performance.now();
        out = await sess.run(feeds);
        times.push(performance.now() - t);
        feedBack(feeds, out);   // như vòng đo thật: trạng thái của lượt trước
        if (i % 5 === 4) { li.textContent = `Đo: ${i + 1}/${n}`; await new Promise((r) => setTimeout(r)); }
        if (i % 250 === 249)   // nhật ký về laptop: nếu tab bị đóng giữa chừng, biết đã chạy được bao nhiêu lần
          fetch("/api/bench/result", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ kind: "bench-progress", ep, model, done: i + 1, of: n, last_ms: +times[i].toFixed(1) }) }).catch(() => {});
      }
      result.p50_ms = +pct(times, 50).toFixed(1); result.p95_ms = +pct(times, 95).toFixed(1);
      result.mean_ms = +(times.reduce((a, b) => a + b, 0) / n).toFixed(1);
      li.textContent = `Mỗi lần: trung vị ${result.p50_ms} ms · p95 ${result.p95_ms} ms · trung bình ${result.mean_ms} ms (tối đa ~${Math.floor(1000 / result.p50_ms)} lần/giây)`;
      const got = out.outputs.data;
      if (reference && reference.outputs.length === got.length) {
        let maxAbs = 0, at = 0;
        for (let i = 0; i < got.length; i++) { const d = Math.abs(got[i] - reference.outputs[i]); if (d > maxAbs || Number.isNaN(d)) { maxAbs = d; at = i; } }
        result.max_abs_diff = +maxAbs.toPrecision(3); result.max_diff_at = at;
        result.worst = { want: +reference.outputs[at].toPrecision(5), got: +got[at].toPrecision(5) };
        result.heads = {};   // sai khác lớn nhất theo từng đầu ra (bảng output_slices trong metadata của model)
        for (const [name, a, b] of HEADS) {
          let m = 0, bad = 0;
          for (let i = a; i < b; i++) { const d = Math.abs(got[i] - reference.outputs[i]); m = Math.max(m, d); bad += d > .05 * Math.max(1, Math.abs(reference.outputs[i])); }
          result.heads[name] = { max: +m.toPrecision(3), bad };
          line(`  ${name} (${b - a}): lệch tối đa ${result.heads[name].max}, ${bad} giá trị lệch > 5%`);
        }
        line(`  chỗ lệch nhất: phần tử ${at}, laptop ${result.worst.want}, máy này ${result.worst.got}`);
        line(`So với laptop (ONNX Runtime CPU, bản FP16): sai khác lớn nhất ${result.max_abs_diff} ở phần tử ${at} / ${got.length}`
          + (model.includes("fp32") ? " (bản FP32 lệch tới ~0,05 là bình thường)" : ""));
      } else line("Không có reference.json để so đầu ra");
      await sess.release();
      state("Xong", "ok");
    } catch (e) {
      result.error = String(e && e.message ? e.message : e) + (e && e.name && e.name !== "Error" ? ` [${e.name}]` : "");
      $("b-err").textContent = result.error; state("Lỗi", "bad");
    } finally {
      $("b-run").disabled = false;
      fetch("/api/bench/result", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(result) })
        .then((r) => line(r.ok ? "Đã gửi kết quả về laptop" : `Không gửi được kết quả về laptop (lỗi ${r.status})`))
        .catch((e) => line(`Không gửi được kết quả về laptop (${e})`));
    }
  }

  $("b-n").max = 5000;   // chạy dài để thử rò bộ nhớ (13/10/2026: tab bị đóng sau 10–60 s đo trên máy)
  $("b-run").addEventListener("click", run);

  /* ---------- dò rò bộ nhớ (/bench?leak=1) ----------
     13/10/2026: trên iPhone, chạy model liên tục bằng WebGPU (không camera, không vẽ) thì Safari đóng tab sau 250–500 lần.
     Thử lần lượt các chế độ bộ nhớ đệm GPU của onnxruntime-web và cách tạo lại phiên, mỗi cách RUNS lần có đưa trạng thái
     vào lượt sau. Trước mỗi cách ghi vào localStorage; tab bị đóng và trang tải lại thì cách đó được ghi là "sập", gửi về
     laptop và tự chuyển sang cách sau. */
  const VARIANTS = [
    { name: "mặc định" }, { name: "cache simple", cache: "simple" }, { name: "cache lazyRelease", cache: "lazyRelease" },
    { name: "cache disabled", cache: "disabled" }, { name: "mặc định, tạo lại phiên mỗi 200 lần", recreate: 200 },
  ];
  const RUNS = 700, KEY = "rw-leak";
  const post = (o) => fetch("/api/bench/result", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind: "leak", ua: navigator.userAgent, ...o }) }).catch(() => {});
  async function leakVariant(v, idx, prog) {
    const ep = v.cache ? [{ name: "webgpu", storageBufferCacheMode: v.cache }] : ["webgpu"];
    const make = () => ort.InferenceSession.create(models["gr14VinAI.mixed.onnx"], { executionProviders: ep, graphOptimizationLevel: "all" });
    let sess = await make();
    const feeds = { ...policyFeeds(sess.inputNames), new_img: pattern([2, 6, 128, 256], 7, 13), state_img_q: pattern([2, 5, 6, 128, 256], 3, 5) };
    const li = line(`${v.name}: 0/${RUNS}`), t0 = performance.now();
    for (let i = 0; i < RUNS; i++) {
      if (v.recreate && i && i % v.recreate === 0) { await sess.release(); sess = await make(); }
      const out = await sess.run(feeds);
      prog.done = i + 1;
      feedBack(feeds, out);
      if (i % 25 === 24) { li.textContent = `${v.name}: ${i + 1}/${RUNS}`; await new Promise((r) => setTimeout(r)); }
      if (i % 100 === 99) post({ stage: "progress", variant: idx, name: v.name, done: i + 1 });
    }
    await sess.release();
    return Math.round((performance.now() - t0) / RUNS);
  }
  async function leakRun() {
    let st = JSON.parse(localStorage.getItem(KEY) || '{"idx":0,"results":[]}');
    if (st.running) {   // trang vừa được tải lại khi đang chạy: cách đó làm sập tab
      st.results.push({ name: VARIANTS[st.idx].name, ok: false });
      post({ stage: "crashed", variant: st.idx, name: VARIANTS[st.idx].name });
      st = { idx: st.idx + 1, results: st.results, running: false };
      localStorage.setItem(KEY, JSON.stringify(st));
    }
    $("b-out").replaceChildren();
    for (const r of st.results) line(`${r.name}: ${r.ok ? `chạy hết ${RUNS} lần (${r.ms} ms/lần)` : r.error ? `lỗi sau ${r.done} lần: ${r.error}` : "tab bị đóng"}`);
    if (st.idx >= VARIANTS.length) { line("Đã thử hết; kết quả đã gửi về laptop."); state("Xong", "ok"); post({ stage: "done", results: st.results }); return; }
    state("Đang dò…", "run");
    ort.env.wasm.wasmPaths = "/ortweb/"; ort.env.wasm.numThreads = 1; ort.env.wasm.proxy = false;
    if (!wasmBinary) wasmBinary = await fetchBytes(WASM, "thư viện WebAssembly");
    ort.env.wasm.wasmBinary = wasmBinary;
    if (!models["gr14VinAI.mixed.onnx"]) models["gr14VinAI.mixed.onnx"] = await fetchBytes("/ortweb/gr14VinAI.mixed.onnx", "model");
    for (; st.idx < VARIANTS.length; st.idx++) {
      localStorage.setItem(KEY, JSON.stringify({ ...st, running: true }));
      post({ stage: "start", variant: st.idx, name: VARIANTS[st.idx].name });
      const prog = { done: 0 };
      let ms;
      try { ms = await leakVariant(VARIANTS[st.idx], st.idx, prog); }
      catch (e) {   // lỗi ORT/WebGPU: WASM và thiết bị GPU trong trang này đã hỏng, chạy tiếp ở đây chỉ lỗi dây chuyền
        const error = String(e && e.message ? e.message : e).slice(0, 300);
        st.results.push({ name: VARIANTS[st.idx].name, ok: false, error, done: prog.done });
        post({ stage: "error", variant: st.idx, name: VARIANTS[st.idx].name, done: prog.done, error });
        localStorage.setItem(KEY, JSON.stringify({ ...st, idx: st.idx + 1, running: false }));
        line(`${VARIANTS[st.idx].name}: lỗi sau ${prog.done} lần; tải lại trang sau 5 giây để thử cách tiếp theo`);
        if (st.idx + 1 < VARIANTS.length) setTimeout(() => location.reload(), 5000); else setTimeout(leakRun, 0);
        return;
      }
      st.results.push({ name: VARIANTS[st.idx].name, ok: true, ms });
      post({ stage: "ok", variant: st.idx, name: VARIANTS[st.idx].name, ms });
      localStorage.setItem(KEY, JSON.stringify({ ...st, idx: st.idx + 1, running: false }));
    }
    localStorage.setItem(KEY, JSON.stringify({ ...st, running: false }));
    leakRun();
  }
  if (new URLSearchParams(location.search).get("leak") === "1") {
    const btn = Object.assign(document.createElement("button"), { type: "button", className: "btn primary ph-go", textContent: "Dò rò bộ nhớ (tự chạy tiếp sau khi tải lại)" });
    const reset = Object.assign(document.createElement("button"), { type: "button", className: "btn small", textContent: "Làm lại từ đầu" });
    $("b-run").before(btn); $("b-run").before(reset);
    btn.addEventListener("click", () => leakRun().catch((e) => {   // lỗi (không phải tab bị đóng): bỏ cờ đang chạy
      const st = JSON.parse(localStorage.getItem(KEY) || "null");
      if (st) localStorage.setItem(KEY, JSON.stringify({ ...st, running: false }));
      $("b-err").textContent = String(e); post({ stage: "error", error: String(e) });
    }));
    reset.addEventListener("click", () => { localStorage.removeItem(KEY); $("b-out").replaceChildren(); line("Đã xoá kết quả dò"); });
    const st = JSON.parse(localStorage.getItem(KEY) || "null");
    if (st && (st.running || st.idx > 0) && st.idx < VARIANTS.length) setTimeout(() => btn.click(), 4000);   // (4 s để GPU của Safari hồi sau khi tab bị đóng) tự chạy tiếp sau khi tab bị tải lại
  }
  // Bản FP16 hỗn hợp (13/10/2026): trên WebGPU của iPhone, tổng bình phương của bước chuẩn hoá L2 (~81 nghìn) vượt FP16
  // (tối đa 65504) nên làn và xe dẫn đầu sai; bản này tính riêng bước đó bằng FP32. Thêm bằng JS: bench.html đọc lúc khởi động.
  $("b-model").prepend(Object.assign(document.createElement("option"), { value: "gr14VinAI.mixed.onnx", textContent: "FP16 hỗn hợp (40 MB, chuẩn hoá L2 bằng FP32)" }));
  $("b-model").value = "gr14VinAI.mixed.onnx";
  const clear = Object.assign(document.createElement("button"), { type: "button", className: "btn small", id: "b-clear", textContent: "Xoá bản đã lưu" });
  $("b-run").after(clear);   // tạo bằng JS: bench.html được server đọc một lần lúc khởi động
  clear.addEventListener("click", async () => {
    try { await caches.delete(CACHE); } catch { /* không có Cache Storage */ }
    for (const k of Object.keys(models)) delete models[k];
    wasmBinary = null; $("b-out").replaceChildren(); line("Đã xoá bản đã lưu: lần chạy tới sẽ tải lại");
  });
})();
