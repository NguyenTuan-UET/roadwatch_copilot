(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const registering = location.pathname === "/register";
  document.title = `${registering ? "Đăng ký" : "Đăng nhập"} · RoadWatch Copilot`;
  $("auth-title").textContent = registering ? "Bắt đầu cùng RoadWatch" : "Chào mừng trở lại";
  $(registering ? "register-tab" : "login-tab").setAttribute("aria-current", "page");
  $("auth-description").textContent = registering ? "Tạo tài khoản để chạy video và xem cảnh báo trực tiếp." : "Đăng nhập để sử dụng RoadWatch.";
  $("auth-submit").textContent = registering ? "Tạo tài khoản" : "Đăng nhập";
  $("password").autocomplete = registering ? "new-password" : "current-password";
  $("confirm-field").hidden = !registering;
  $("confirm-password").required = registering;
  const next = new URLSearchParams(location.search).get("next") || "/app";
  const destination = ["/app", "/engineer", "/judge"].includes(next.split(/[?#]/)[0]) ? next : "/app";
  for (const id of ["login-tab", "register-tab"]) $(id).href += `?next=${encodeURIComponent(destination)}`;
  $("auth-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = $("auth-error"), button = $("auth-submit");
    error.hidden = true;
    if (registering && $("password").value !== $("confirm-password").value) {
      error.textContent = "Mật khẩu nhập lại chưa khớp."; error.hidden = false; return;
    }
    button.disabled = true; button.textContent = "Đang xử lý…";
    try {
      const response = await fetch(`/api/auth/${registering ? "register" : "login"}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: $("username").value.trim(), password: $("password").value }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Vui lòng kiểm tra tên đăng nhập và mật khẩu.");
      location.assign(destination);
    } catch (exc) {
      error.textContent = exc instanceof TypeError ? "Mất kết nối tới server. Hãy thử lại." : exc.message;
      error.hidden = false;
    } finally {
      button.disabled = false; button.textContent = registering ? "Tạo tài khoản" : "Đăng nhập";
    }
  });
})();
