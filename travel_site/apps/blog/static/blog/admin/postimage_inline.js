// apps/blog/static/blog/admin/postimage_inline.js
(function () {
  function copyText(text) {
    if (!text) return;

    // 최신 브라우저
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text);
      return;
    }

    // fallback
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(ta);
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".js-copy-token");
    if (!btn) return;
    const token = btn.getAttribute("data-token");
    copyText(token);

    // 간단 피드백(원하면 제거 가능)
    const old = btn.textContent;
    btn.textContent = "복사됨";
    setTimeout(() => (btn.textContent = old), 700);
  });
})();
