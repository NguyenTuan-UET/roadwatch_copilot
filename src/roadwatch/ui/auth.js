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
  $("role-field").hidden = !registering;
  $("confirm-password").required = registering;
  const next = new URLSearchParams(location.search).get("next") || "/app";
  const destination = ["/app", "/engineer", "/judge"].includes(next.split(/[?#]/)[0]) ? next : "/app";
  for (const id of ["login-tab", "register-tab"]) $(id).href += `?next=${encodeURIComponent(destination)}`;
  const other = registering ? ["Đã có tài khoản?", "login-tab", "Đăng nhập"] : ["Chưa có tài khoản?", "register-tab", "Đăng ký"];
  const link = Object.assign(document.createElement("a"), { href: $(other[1]).href, textContent: other[2] });
  $("auth-switch").append(`${other[0]} `, link);

  // hiện / ẩn mật khẩu
  for (const eye of document.querySelectorAll(".eye")) eye.addEventListener("click", () => {
    const input = $(eye.dataset.for), show = input.type === "password";
    input.type = show ? "text" : "password"; eye.setAttribute("aria-pressed", String(show));
  });
  // độ mạnh mật khẩu và nhập lại (chỉ khi đăng ký); chỉ là gợi ý, server vẫn chỉ yêu cầu tối thiểu 8 ký tự
  if (registering) {
    $("strength").hidden = false; $("password-help").hidden = true;
    const LABELS = ["", "Yếu", "Trung bình", "Khá", "Mạnh"];
    const update = () => {
      const pw = $("password").value, confirm = $("confirm-password").value;
      const rules = { len: pw.length >= 8, mix: /[a-zA-Z]/.test(pw) && /\d/.test(pw), space: pw.length > 0 && !/\s/.test(pw) };
      for (const li of document.querySelectorAll(".rules li")) li.classList.toggle("ok", rules[li.dataset.rule]);
      const score = !pw ? 0 : Object.values(rules).filter(Boolean).length + (pw.length >= 12 && /[^a-zA-Z0-9]/.test(pw) ? 1 : 0);
      $("strength").dataset.score = score; $("strength-label").textContent = LABELS[score];
      $("confirm-help").textContent = !confirm ? "" : confirm === pw ? "Mật khẩu khớp." : "Mật khẩu nhập lại chưa khớp.";
      $("confirm-help").className = !confirm ? "muted" : confirm === pw ? "match" : "mismatch";
    };
    $("password").addEventListener("input", update); $("confirm-password").addEventListener("input", update); update();
  }
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
        body: JSON.stringify({ username: $("username").value.trim(), password: $("password").value,
          ...(registering ? { role: $("role").value } : {}) }),
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
