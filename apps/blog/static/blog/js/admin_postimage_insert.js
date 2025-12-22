// admin_postimage_insert.js
(function () {
  "use strict";

  const DEDUPE = true; // ✅ 같은 토큰이 이미 있으면 재삽입 방지

  function normalizeNewline(s) {
    return (s || "").replace(/\r\n/g, "\n");
  }

  function insertAtCursor(textarea, text) {
    const value = normalizeNewline(textarea.value);
    const token = String(text || "").trim();
    if (!token) return;

    // ✅ 중복 방지(원하면 끌 수 있음)
    if (DEDUPE && value.includes(token)) {
      // 이미 있으면 해당 위치로 스크롤/커서 이동만
      const idx = value.indexOf(token);
      textarea.focus();
      textarea.selectionStart = idx;
      textarea.selectionEnd = idx + token.length;
      textarea.scrollTop = textarea.scrollHeight;
      return;
    }

    const start = Number.isFinite(textarea.selectionStart) ? textarea.selectionStart : value.length;
    const end = Number.isFinite(textarea.selectionEnd) ? textarea.selectionEnd : value.length;

    const before = value.slice(0, start);
    const after = value.slice(end);

    // 줄바꿈 보정:
    // - before가 비어있지 않고 마지막이 공백/줄바꿈이 아니면 한 줄 내려서 넣기
    // - after가 비어있지 않고 시작이 줄바꿈이 아니면 한 줄 내려서 이어지게
    const needPrefixNl = before && !/[ \t\n]$/.test(before);
    const needSuffixNl = after && !/^[ \t\n]/.test(after);

    const prefix = needPrefixNl ? "\n" : "";
    const suffix = needSuffixNl ? "\n" : (after ? "" : "\n"); // 끝이면 한 줄 내려 마무리

    const nextValue = before + prefix + token + suffix + after;
    textarea.value = nextValue;

    const caret = (before + prefix + token + suffix).length;
    textarea.focus();
    textarea.selectionStart = textarea.selectionEnd = caret;

    // ✅ Django admin 변경 감지
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.dispatchEvent(new Event("change", { bubbles: true }));
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".js-insert-token");
    if (!btn) return;

    const token = btn.getAttribute("data-token");
    if (!token) return;

    const textarea = document.getElementById("id_content");
    if (!textarea) {
      alert("본문 입력창(id_content)을 찾지 못했습니다.");
      return;
    }

    insertAtCursor(textarea, token);
  });
})();
