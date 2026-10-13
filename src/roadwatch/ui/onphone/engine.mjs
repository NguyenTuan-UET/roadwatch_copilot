/* Đo ngay trên điện thoại, không gửi ảnh về laptop: camera -> nắn ảnh (prep.mjs) -> gr14VinAI trên GPU của máy
   (onnxruntime-web, WebGPU; bản FP16 hỗn hợp, đã thử trên iPhone 13/10/2026) -> đọc đầu ra (parse.mjs) -> BT-A
   (track.mjs) -> BT-B (decide.mjs). Mỗi khung tạo một trạng thái cùng dạng LiveStatus của server (job.py) và hình
   làn/xe dẫn đầu (geometry.overlay), nên màn đo của /phone dùng lại được nguyên.
   Thời gian là đồng hồ phiên (giây từ lúc bắt đầu, performance.now), như đường đo trực tiếp của server (spec 3.3).
   Đầu vào góc rộng: WIDE = "dup" (ảnh hẹp nhân đôi): nhanh hơn, độ phủ luôn đủ khi điện thoại chúc lên/xuống, và Lab
   dùng cách này trên comma2k19 cho kết quả so với radar tốt hơn; server dùng "auto". */
import { fetchBytes } from "./assets.mjs";
import { focalPxFromMm, overlay } from "./geometry.mjs";
import { parseOutputs } from "./parse.mjs";
import { GpuPrep } from "./gpuprep.mjs";
import { inferFrame } from "./inference.mjs";
import { prepFromRGBA, sampleRect, shiftWarps } from "./prep.mjs";
import { Pipeline } from "./track.mjs";
import { Decider, PHRASES } from "./decide.mjs";

export const MODEL_URL = "/ortweb/gr14VinAI.mixed.onnx";
const ORT_URL = "/ortweb/ort.webgpu.min.js", WASM_URL = "/ortweb/ort-wasm-simd-threaded.asyncify.wasm";
export const WIDE = "dup";
const TICK_MS = 50;   // model học ở 20 Hz: không chạy nhanh hơn
const rnd = (x, n = 1) => (x === null || x === undefined || !Number.isFinite(x) ? null : Math.round(x * 10 ** n) / 10 ** n);
const deg = (r) => r * 180 / Math.PI;
const pct = (xs, p) => { if (!xs.length) return null; const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(p / 100 * s.length))]; };

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (typeof globalThis.ort !== "undefined") return resolve();
    const s = Object.assign(document.createElement("script"), { src, onload: resolve, onerror: () => reject(new Error(`không tải được ${src}`)) });
    document.head.append(s);
  });
}

/** Tải thư viện và model (lưu lại trên máy), tạo phiên. progress(text) để hiện tiến độ. */
export async function loadModel(progress = () => {}, ep = "webgpu", modelUrl = MODEL_URL) {
  if (ep === "webgpu" && !navigator.gpu) throw new Error("Trình duyệt chưa bật WebGPU (Safari trên iOS 26, hoặc bật trong Feature Flags)");
  await loadScript(ORT_URL);
  const ort = globalThis.ort;
  ort.env.wasm.wasmPaths = "/ortweb/"; ort.env.wasm.numThreads = 1; ort.env.wasm.proxy = false;
  ort.env.wasm.wasmBinary = await fetchBytes(WASM_URL, "thư viện", progress);
  const model = await fetchBytes(modelUrl, "model", progress);
  progress("Đang chuẩn bị model trên GPU…");
  // Trạng thái 5 khung (uint8) đi qua CPU: để trên GPU (preferredOutputLocation) thì giải phóng tensor lỗi, và các phép
  // đầu của model trên uint8 chạy ở CPU nên đằng nào cũng phải về (thử trên Chrome 13/10/2026)
  const session = await ort.InferenceSession.create(model, { executionProviders: [ep], graphOptimizationLevel: "all" });
  ort.env.wasm.wasmBinary = undefined;   // đã nạp xong: trả lại 27 MB (iPhone đóng tab khi trang dùng quá nhiều bộ nhớ)
  return session;
}

/** Tốc độ GPS trên đồng hồ phiên, như phone.LiveGps: tin mới nhất còn mới (≤ 3 s), bỏ tin sai số > 50 m. */
export class PhoneGps {
  static STALE_S = 3; static MAX_ACCURACY_M = 50;
  constructor() { this.rows = []; }
  add(t, { speed, lat, lon, acc }) {
    if (![lat, lon, acc].every(Number.isFinite) || acc > PhoneGps.MAX_ACCURACY_M) return;
    let v = Number.isFinite(speed) && speed >= 0 ? speed : null;
    const prev = this.rows[this.rows.length - 1];
    if (v === null && prev && t > prev.t) {   // iOS có lúc không cho tốc độ: tính từ vị trí trước
      const R = 6371000, p1 = prev.lat * Math.PI / 180, p2 = lat * Math.PI / 180;
      const a = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin((lon - prev.lon) * Math.PI / 360) ** 2;
      v = 2 * R * Math.asin(Math.sqrt(a)) / (t - prev.t);
    }
    if (v !== null && v > 90) return;
    this.rows.push({ t, v: v === null ? NaN : v, lat, lon });
    if (this.rows.length > 600) this.rows.shift();
  }
  speedAt(pts) {
    for (let i = this.rows.length - 1; i >= 0; i--) {
      const r = this.rows[i];
      if (r.t <= pts && Number.isFinite(r.v)) return pts - r.t <= PhoneGps.STALE_S ? r.v : NaN;
    }
    return NaN;
  }
}

/** Đầu vào model bằng đường CPU (vẽ vùng cắt lên canvas, nắn bằng JS): để so với đường GPU khi chẩn đoán. */
function cpuInput(v, canvas, ctx, warps, w, h) {
  const [cx, cy, cw, ch] = sampleRect(warps, w, h);
  if (canvas.width < cw || canvas.height < ch) { canvas.width = Math.max(canvas.width, cw); canvas.height = Math.max(canvas.height, ch); }
  ctx.drawImage(v, cx, cy, cw, ch, 0, 0, cw, ch);
  return prepFromRGBA(ctx.getImageData(0, 0, cw, ch).data, cw, ch, shiftWarps(warps, cx, cy));
}

/** Độ sáng trung bình kênh Y, tỉ lệ điểm 0 và độ lệch của hai đầu vào (chẩn đoán ảnh GPU sai). */
function compareInputs(a, b) {
  const plane = 128 * 256, stat = (x) => { let s = 0, z = 0; for (let k = 0; k < 4 * plane; k++) { s += x[k]; z += x[k] === 0; } return [s / (4 * plane), z / (4 * plane)]; };
  let max = 0, sum = 0, flipSum = 0;
  for (let k = 0; k < a.length / 2; k++) { const d = Math.abs(a[k] - b[k]); max = Math.max(max, d); sum += d; }
  for (let r = 0; r < 128; r++) for (let c = 0; c < 256; c++) flipSum += Math.abs(a[r * 256 + c] - b[(127 - r) * 256 + c]);   // lật dọc?
  const [ga, gz] = stat(a), [ca, cz] = stat(b);
  const rnd2 = (x) => Math.round(x * 100) / 100;
  return { gpu_y_mean: rnd2(ga), cpu_y_mean: rnd2(ca), gpu_zero: rnd2(gz), cpu_zero: rnd2(cz), max_diff: max,
           mean_diff: rnd2(sum / (a.length / 2)), mean_diff_if_flipped: rnd2(flipSum / plane),
           u_gpu: a[4 * plane + 64 * 256 + 128], u_cpu: b[4 * plane + 64 * 256 + 128], v_gpu: a[5 * plane + 64 * 256 + 128], v_cpu: b[5 * plane + 64 * 256 + 128] };
}

/** Một lần đo: start() chạy vòng lặp tới khi stop(). onStatus(s) mỗi khung (dạng LiveStatus), onOverlay(o) hình làn. */
export class DeviceRun {
  constructor({ session, video, dCamBumper, fMm, gps, onStatus, onOverlay = () => {}, report = () => {}, prep = "cpu" }) {
    Object.assign(this, { session, video, dCamBumper, fMm, gps, onStatus, onOverlay, report, prep });
    this.running = false; this.runId = `device-${Date.now().toString(16)}`;
    this.t0 = performance.now();   // đồng hồ phiên: khung và tin GPS cùng tính từ đây
  }

  async start() {
    const ort = globalThis.ort, v = this.video;
    const w = v.videoWidth & ~1, h = v.videoHeight & ~1;
    if (!w || !h) throw new Error("Chưa có hình camera");
    if (h > w) throw new Error("Camera đang dọc: hãy xoay ngang điện thoại");
    // Mặc định (prep = "cpu"): chỉ vẽ và đọc vùng model dùng lên một canvas nhỏ rồi nắn bằng JS (prep.mjs).
    // prep = "gpu" (thử nghiệm): khung camera -> texture -> shader nắn ảnh -> 393 KB về CPU (gpuprep.mjs). Trên Chrome
    // headless, khi trang đã nạp onnxruntime-web, mapAsync của device WebGPU riêng lỗi ("external Instance reference"),
    // dù shader cho kết quả như prep.mjs khi chạy một mình (13/10/2026); lỗi thì tự quay về CPU và ghi vào nhật ký.
    let gpu = null;
    if (this.prep === "gpu" && navigator.gpu) {
      try {
        this.adapter = await navigator.gpu.requestAdapter();   // giữ tham chiếu: adapter bị dọn thì device hỏng (Chrome)
        gpu = new GpuPrep(await this.adapter.requestDevice(), w, h);
      }
      catch (e) { this.report({ stage: "gpu prep unavailable", error: String(e) }); }
    }
    const canvas = document.createElement("canvas"), ctx = canvas.getContext("2d", { willReadFrequently: true });
    const fy = focalPxFromMm(this.fMm, w);
    const pipe = this.pipe = new Pipeline({ w, h, fy, dCamBumper: this.dCamBumper, wide: WIDE });
    const dec = new Decider(), events = [], said = { emergency: 0, warning: 0, info: 0 }, onsets = { ...said };
    let state = new ort.Tensor("uint8", new Uint8Array(2 * 5 * 6 * 128 * 256), [2, 5, 6, 128, 256]);
    const input = new Uint8Array(2 * 6 * 128 * 256), ms = [], t0 = this.t0;
    let i = 0, prevRaw = new Set(), last = t0 - TICK_MS, prevPts = 0;
    this.running = true;
    this.onStatus({ state: "running", run_id: this.runId, events: [] });
    this.report({ stage: "start", size: [w, h], fy: Math.round(fy), prep: gpu ? "gpu" : "cpu" });
    let nextReport = t0 + 10000;
    try {
      while (this.running) {
      // luôn nhường lượt ít nhất một lần: khi model chạy lâu hơn 50 ms (CPU), không nhường thì trang không vẽ lại được
      const wait = TICK_MS - (performance.now() - last);
      await new Promise((r) => setTimeout(r, Math.max(0, wait)));
      if (!this.running) break;
      const tick = last = performance.now(), pts = (tick - t0) / 1000;
      const [cx, cy, cw, ch] = sampleRect(pipe.warps, w, h);   // vùng model dùng
      let newImg = null;
      if (gpu) {
        try {
          newImg = new ort.Tensor("uint8", await gpu.run(v, pipe.warps, input), [2, 6, 128, 256]);
          if (i === 1 || i === 50 || i === 200) this.report({ stage: "gpu vs cpu input", frame: i, ...compareInputs(input, cpuInput(v, canvas, ctx, pipe.warps, w, h)) });
        }
        catch (e) {
          this.report({ stage: "gpu prep failed, using cpu", error: String(e) });
          try { gpu.destroy(); } catch { /* đã hỏng */ }
          gpu = null;
        }
      }
      if (!newImg) {
        if (canvas.width < cw || canvas.height < ch) { canvas.width = Math.max(canvas.width, cw); canvas.height = Math.max(canvas.height, ch); }
        ctx.drawImage(v, cx, cy, cw, ch, 0, 0, cw, ch);
        prepFromRGBA(ctx.getImageData(0, 0, cw, ch).data, cw, ch, shiftWarps(pipe.warps, cx, cy), input);
        newImg = new ort.Tensor("uint8", input, [2, 6, 128, 256]);
      }
      const tPrep = performance.now();
      const previousState = state; state = null;   // inferFrame giải phóng trạng thái cũ cả khi model ném lỗi
      const frame = await inferFrame(this.session, newImg, previousState, parseOutputs);
      state = frame.nextState;
      const tModel = performance.now();
      // dt thật giữa hai khung (khung đầu: 50 ms): vận tốc model và Kalman theo nhịp thật khi máy chạy dưới 20 Hz
      const r = pipe.update(frame.parsed, pts, this.gps.speedAt(pts), i ? pts - prevPts : TICK_MS / 1000);
      prevPts = pts;
      const calibrated = r.status === "calibrated";
      const tb = performance.now();
      const d = dec.step(pts, r.gap_m, r.ego_speed_mps, r.ttc_s, calibrated, !r.status.startsWith("unreliable"));
      const bUs = (performance.now() - tb) * 1000;
      for (const k of d.raw) if (!prevRaw.has(k)) onsets[k]++;
      prevRaw = d.raw;
      if (d.say) { said[d.say]++; events.push({ t_s: rnd(pts, 2), kind: d.say, text: PHRASES[d.say], reason: d.reason }); }
      ms.push(performance.now() - tick); if (ms.length > 600) ms.shift();
      this.onOverlay({ frame: i, ...overlay(pipe.K, r, w, h) });
      this.onStatus({   // cùng dạng schemas.LiveStatus (job.py), thêm timing để biết chậm ở đâu
        state: "running", run_id: this.runId,
        measure: {
          frame: i, t_s: rnd(pts, 2), ego_kmh: rnd(r.ego_speed_mps * 3.6), ttc_s: rnd(r.ttc_s),
          ego_source: r.gps_speed_mps !== null ? "gps" : "model", model_kmh: rnd(r.model_speed_mps * 3.6),
          gps: { state: "synced", offset_s: 0, corr: null },
          lead_raw_m: rnd(r.lead_raw_m === null ? null : r.lead_raw_m - this.dCamBumper),
          lead: { prob: rnd(r.lead_prob, 2), gap_m: rnd(r.gap_m), speed_kmh: rnd(r.gap_m !== null ? r.lead_speed_mps * 3.6 : null),
                  gap_std_m: rnd(r.gap_m !== null ? r.gap_std_m : null) },
          calibration: { status: r.status, calibrated, flags: [], fy_px: Math.round(fy), fy_state: "từ tiêu cự mm",
                         pitch_deg: rnd(deg(r.rpy[1]), 2), yaw_deg: rnd(deg(r.rpy[2]), 2), height_m: rnd(r.height_m, 2),
                         coverage: rnd(pipe.coverage, 3), remounts: 0 },
        },
        decision: { level: d.level, say: d.say, reason: d.reason, threshold_m: d.threshold_m, latency_us: Math.round(bUs) },
        ops: { fps: rnd((i + 1) / ((performance.now() - t0) / 1000)), video_fps: 20, bad_frames: 0,
               latency: { last_ms: rnd(ms[ms.length - 1]), p50_ms: rnd(pct(ms, 50)), p95_ms: rnd(pct(ms, 95)) },
               raw_onsets: { ...onsets }, said: { ...said },
               device: { prep_ms: rnd(tPrep - tick), model_ms: rnd(tModel - tPrep), size: [w, h], prep: gpu ? "GPU" : "CPU" } },
        sample: { t_s: rnd(pts, 2), gap_m: rnd(r.gap_m), threshold_m: d.threshold_m, ttc_s: rnd(r.ttc_s, 2) },
        events: events.slice(-30),
      });
      if (i === 0 || performance.now() > nextReport) {
        nextReport = performance.now() + 5000;   // dày để biết lúc tab bị đóng
        this.report({ stage: i ? "running" : "first frame", frame: i, t_s: rnd(pts, 1), fps: rnd((i + 1) / ((performance.now() - t0) / 1000)),
                      prep_ms: rnd(tPrep - tick), model_ms: rnd(tModel - tPrep), read: gpu ? "gpu" : [cw, ch], status: r.status, gap_m: rnd(r.gap_m) });
      }
      i++;
      }
    } finally {
      if (state) state.dispose();
      if (gpu) try { gpu.destroy(); } catch (e) { this.report({ stage: "gpu prep release error", error: String(e) }); }
    }
    this.report({ stage: "stop", frames: i, said });
    this.onStatus({ state: "stopped", run_id: this.runId, events: events.slice(-30),
                    ops: { said: { ...said }, raw_onsets: { ...onsets }, fps: rnd(i / ((performance.now() - t0) / 1000)) } });
  }

  stop() { this.running = false; }
}
