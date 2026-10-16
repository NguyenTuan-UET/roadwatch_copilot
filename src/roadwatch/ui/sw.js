/* Cho /phone mở được khi mất mạng hoặc laptop tắt: giữ trang, mã, câu nói thu sẵn và thư viện onnxruntime-web trong
   Cache Storage của trình duyệt. Có mạng thì lấy bản mới nhất từ laptop (và cập nhật bản lưu); không được trong NET_MS
   thì dùng bản đã lưu. File model và .wasm không qua đây: onphone/assets.mjs đã tự lưu (cache roadwatch-ortweb-v4).
   Cần HTTPS (hoặc localhost) và phải mở /phone một lần khi có mạng. */
const CACHE = "roadwatch-shell-v1", NET_MS = 4000;
const SHELL = [
  "/phone", "/ui/app.css", "/ui/phone.css", "/ui/phone.js", "/ui/apple-touch-icon.png", "/ui/phone-bg.jpg", "/ui/rotate.mp4",
  ...["assets", "backend", "captured", "decide", "engine", "geometry", "gpuprep", "inference", "jitter", "lanes", "num", "parse", "prep", "track"]
    .map((n) => `/ui/onphone/${n}.mjs`),
  "/ortweb/1.20.1/ort.webgpu.min.js", "/ortweb/1.20.1/ort-wasm-simd-threaded.jsep.mjs",
  "/api/phrases/info", "/api/phrases/warning", "/api/phrases/emergency",
];
const covers = (path) => SHELL.includes(path);

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    // từng file một: thiếu một file (ví dụ chưa có câu nói) không làm hỏng cả lần cài
    await Promise.all(SHELL.map((url) => store(cache, new Request(url, { cache: "reload" })).catch(() => {})));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) if (name.startsWith("roadwatch-shell-") && name !== CACHE) await caches.delete(name);
    await self.clients.claim();
  })());
});

/** Tải và lưu; không lưu trang đăng nhập (chuyển hướng) hay lỗi. */
async function store(cache, request) {
  const r = await fetch(request);
  if (r.ok && !r.redirected && r.type === "basic") await cache.put(new Request(new URL(request.url).pathname), r.clone());
  return r;
}

async function answer(request, path) {
  const cache = await caches.open(CACHE);
  const key = new Request(path);
  let timer;
  const timeout = new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("timeout")), NET_MS); });
  try {
    const r = await Promise.race([store(cache, request), timeout]);
    if (r.ok || !(await cache.match(key))) return r;   // 401/404 thật thì báo; đừng che bằng bản cũ trừ khi mạng hỏng
    return (await cache.match(key)) || r;
  } catch {
    return (await cache.match(key, { ignoreSearch: true })) || Response.error();
  } finally { clearTimeout(timer); }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || request.headers.has("range")) return;
  if (covers(url.pathname)) event.respondWith(answer(request, url.pathname));
});
