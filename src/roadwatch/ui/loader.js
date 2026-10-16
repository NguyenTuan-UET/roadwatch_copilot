// Màn hình Loading có mascot: chặn trang cho tới khi tải hết asset, rồi mascot nháy mắt và biến mất.
// Nhúng ở <head> bằng thẻ script đồng bộ để lớp phủ có ngay từ khung hình đầu.
//   data-auto="load"   tự kết thúc khi window "load" xong (trang tĩnh);
//   data-images="a,b"  các ảnh cần tải trước, chờ đủ rồi mới mở;
// không có data-auto thì trang tự gọi RoadWatchLoader.finish() khi sẵn sàng (buồng lái). Quá 25 giây thì mở luôn để không kẹt.
(function () {
  "use strict";
  var me = document.currentScript, root = document.documentElement;
  var el = document.createElement("div");
  el.id = "rw-loader"; el.setAttribute("role", "status"); el.setAttribute("aria-live", "polite");
  el.innerHTML = '<style>' +
    '#rw-loader{position:fixed;inset:0;z-index:2147483000;display:grid;place-content:center;justify-items:center;gap:16px;background:radial-gradient(ellipse at 50% 55%,#0e1823,#04070b 75%);color:#b8c7d3;font:600 12px/1 system-ui,sans-serif;letter-spacing:.16em;text-transform:uppercase;transition:opacity .4s ease,visibility .4s}' +
    '#rw-loader.out{opacity:0;visibility:hidden;pointer-events:none}' +
    '#rw-loader canvas{width:min(340px,80vw);height:min(255px,60vw)}' +
    '#rw-loader .bar{width:200px;height:4px;border-radius:2px;background:#1b2834;overflow:hidden}' +
    '#rw-loader .bar i{display:block;width:40%;height:100%;background:#46d6e6;animation:rw-bar 1.1s ease-in-out infinite}' +
    '@keyframes rw-bar{0%{transform:translateX(-100%)}100%{transform:translateX(250%)}}' +
    '@media (prefers-reduced-motion:reduce){#rw-loader .bar i{animation:none;width:100%}}' +
    '</style><canvas aria-hidden="true"></canvas><div class="bar"><i></i></div><span>Đang tải RoadWatch…</span>';
  root.appendChild(el);

  var mascot = null, finished = false, closed = false, pending = 1;   // pending: số việc còn chờ (1 = cờ "finish")

  function load(src) { return new Promise(function (ok, no) { var s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = no; document.head.appendChild(s); }); }
  // mascot nạp riêng; không có WebGL hay lỗi mạng thì chỉ còn thanh chạy, trang vẫn mở bình thường
  load("/ui/vendor/three.min.js").then(function () { return load("/ui/mascot.js"); })
    .then(function () { return window.RoadWatchMascot.start(el.querySelector("canvas")); })
    .then(function (m) { if (closed) m.stop(); else mascot = m; })
    .catch(function () {});

  function close() {
    if (closed) return; closed = true;
    root.classList.remove("rw-booting");
    el.classList.add("out");
    setTimeout(function () { if (mascot) mascot.stop(); el.remove(); }, 500);
  }
  function release() {
    if (--pending > 0 || finished) return;
    finished = true;
    if (!mascot) return close();
    mascot.wink();                     // vào app: nháy mắt rồi biến mất
    setTimeout(close, 900);
  }
  function wait(p) { pending++; p.then(release, release); }

  var imgs = (me && me.dataset.images ? me.dataset.images.split(",") : []);
  imgs.forEach(function (src) { wait(new Promise(function (ok) { var i = new Image(); i.onload = i.onerror = ok; i.src = src; })); });
  if (me && me.dataset.auto === "load") {
    wait(new Promise(function (ok) { if (document.readyState === "complete") ok(); else addEventListener("load", ok); }));
    release();
  }

  window.RoadWatchLoader = { finish: release };
  setTimeout(close, 25000);
})();
