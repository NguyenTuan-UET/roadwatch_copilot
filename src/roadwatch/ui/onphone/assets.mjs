/* Tải thư viện onnxruntime-web và model về điện thoại một lần (như /bench, đã thử trên iPhone 13/10/2026):
   từng đoạn CHUNK bằng HTTP Range, đứt kết nối thì thử lại tới khi STALL_MS không có tiến triển, mỗi đoạn và cả file
   được lưu vào Cache Storage nên lần sau không tải lại và lần tải hỏng thì tải tiếp phần thiếu. */
// đổi tên khi model được dựng lại cùng tên file (v4, 14/10/2026: viết lại phép cho JSEP); xoá bản cũ để không dùng nhầm
const CHUNK = 2 << 20, STALL_MS = 180000, CACHE = "roadwatch-ortweb-v4", OLD = ["roadwatch-ortweb-v1", "roadwatch-ortweb-v2", "roadwatch-ortweb-v3"];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const mb = (n) => (n / 1e6).toFixed(1);

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

/** url -> Uint8Array; progress(text) báo tiến độ để hiện trên trang. */
export async function fetchBytes(url, label, progress = () => {}) {
  let cache = null;
  try {
    for (const name of OLD) await caches.delete(name);
    cache = await caches.open(CACHE);
    const hit = await cache.match(url);
    if (hit) { const b = new Uint8Array(await hit.arrayBuffer()); progress(`${cap(label)}: dùng bản đã lưu (${mb(b.length)} MB)`); return b; }
  } catch { cache = null; }
  const part = (start) => `${url}?part=${start}`;
  const parts = []; let got = 0, total = null;
  while (total === null || got < total) {
    let buf = null;
    if (cache && total !== null) {
      const hit = await cache.match(part(got)).catch(() => null);
      if (hit) buf = new Uint8Array(await hit.arrayBuffer());
    }
    const since = performance.now(); let tries = 0;
    while (!buf) {
      try {
        const r = await fetch(url, { headers: { Range: `bytes=${got}-${got + CHUNK - 1}` }, cache: "no-store" });
        if (r.status === 401) { location.assign(`/login?next=${encodeURIComponent(location.pathname)}`); throw new Error("Cần đăng nhập"); }
        if (r.status !== 206 && r.status !== 200) throw new Error(`lỗi ${r.status}`);
        const b = new Uint8Array(await r.arrayBuffer());
        if (r.status === 200) { parts.length = 0; got = 0; total = b.length; }
        else total = Number((r.headers.get("content-range") || "").split("/")[1]) || got + b.length;
        buf = b;
        if (cache && r.status === 206) await cache.put(part(got), new Response(b)).catch(() => {});
      } catch (e) {
        tries++;
        const waited = performance.now() - since;
        if (waited > STALL_MS) throw new Error(`Không tải được ${label}: mất kết nối hơn ${STALL_MS / 60000} phút (${e.message || e})`);
        progress(`${cap(label)}: đang tải ${mb(got)}${total ? ` / ${mb(total)}` : ""} MB · mất kết nối ${Math.round(waited / 1000)} s, thử lại…`);
        await sleep(Math.min(5000, 1000 * tries));
      }
    }
    parts.push(buf); got += buf.length;
    progress(`${cap(label)}: đang tải ${mb(got)} / ${mb(total)} MB`);
  }
  const out = new Uint8Array(got); let o = 0; for (const p of parts) { out.set(p, o); o += p.length; }
  if (cache) {
    try {
      await cache.put(url, new Response(out, { headers: { "Content-Type": "application/octet-stream" } }));
      for (let st = 0; st < got; st += CHUNK) await cache.delete(part(st));
    } catch { /* hết chỗ: lần sau tải lại */ }
  }
  return out;
}
