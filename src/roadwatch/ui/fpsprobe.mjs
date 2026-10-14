/* Tốc độ khung của video chọn để chạy, ước lượng ngay trong trình duyệt: phát tắt tiếng một lúc và lấy khoảng cách
   mediaTime giữa các khung (requestVideoFrameCallback). Gợi ý cho ô "Tốc độ khung lúc quay" của form tải lên: model đo
   vận tốc từ thời gian giữa hai khung, nên fps nhập sai thì vận tốc sai theo tỉ lệ (phiên Lái thử 14/10/2026: video
   29,97 khung/s chạy với 20 cho tốc độ thấp 1,5 lần). Server cũng kiểm lại bằng ffprobe (model.video_fps). */
export const STANDARD_FPS = [23.976, 24, 25, 29.97, 30, 48, 50, 59.94, 60];

/** times: mediaTime của các khung được trình bày (s), có thể thiếu khung khi máy giải mã không kịp -> fps (chuẩn gần
    nhất nếu lệch dưới 1 %) hoặc null. Khung bị bỏ làm khoảng cách thành bội của chu kỳ khung, nên lấy khoảng cách nhỏ
    điển hình (phân vị 20 %), không lấy trung vị hay tổng số khung. */
export function estimateFps(times) {
  const gaps = [];
  for (let i = 1; i < times.length; i++) if (times[i] > times[i - 1] + 1e-6) gaps.push(times[i] - times[i - 1]);
  if (gaps.length < 5) return null;
  gaps.sort((x, y) => x - y);
  const measured = 1 / gaps[Math.floor(0.2 * gaps.length)];
  const std = STANDARD_FPS.reduce((best, f) => (Math.abs(f - measured) < Math.abs(best - measured) ? f : best));
  return Math.abs(std - measured) / std < 0.02 ? std : Math.round(measured * 100) / 100;
}

const vi = (x) => String(x).replace(".", ",");

/** Gợi ý dưới ô fps: ok khi fps nhập lệch tối đa 5 % so với video. */
export function fpsHint(videoFps, entered) {
  if (!Number.isFinite(videoFps)) return { ok: true, text: "" };
  if (Number.isFinite(entered) && entered > 0 && Math.abs(entered - videoFps) <= 0.05 * videoFps)
    return { ok: true, text: `Video này khoảng ${vi(videoFps)} fps.` };
  const ratio = Number.isFinite(entered) && entered > 0 ? videoFps / entered : null;
  return { ok: false, text: `Video này khoảng ${vi(videoFps)} fps, đang nhập ${Number.isFinite(entered) ? vi(entered) : "—"}: vận tốc sẽ sai khoảng ${ratio ? vi(Math.round(Math.max(ratio, 1 / ratio) * 10) / 10) : "?"} lần.` };
}

/** Phát video tắt tiếng tối đa ~1,5 s và đo; null khi trình duyệt không có requestVideoFrameCallback hoặc không phát được. */
export function measureFps(url) {
  return new Promise((resolve) => {
    const v = Object.assign(document.createElement("video"), { muted: true, playsInline: true, preload: "auto", src: url, playbackRate: 0.5 });   // chậm: giải mã kịp, ít bỏ khung
    if (!("requestVideoFrameCallback" in v)) return resolve(null);
    const times = [];
    const finish = () => { v.pause(); v.removeAttribute("src"); v.load(); resolve(estimateFps(times)); };
    const tick = (_, meta) => { times.push(meta.mediaTime); if (times.length >= 45) finish(); else v.requestVideoFrameCallback(tick); };
    v.requestVideoFrameCallback(tick);
    v.play().catch(() => resolve(null));
    setTimeout(finish, 2500);
  });
}
