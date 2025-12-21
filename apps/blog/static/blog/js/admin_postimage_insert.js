// admin_postimage_insert.js
(function () {
  function insertAtCursor(textarea, text) {
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? textarea.value.length;

    const before = textarea.value.slice(0, start);
    const after = textarea.value.slice(end);

    // 앞/뒤 줄바꿈이 자연스럽게 들어가도록 약간 보정(원하면 수정 가능)
    const prefix = (before && !before.endsWith("\n")) ? "\n" : "";
    const suffix = (!after.startsWith("\n")) ? "\n" : "";

    textarea.value = before + prefix + text + suffix + after;

    const newPos = (before + prefix + text + "\n").length;
    textarea.focus();
    textarea.selectionStart = textarea.selectionEnd = newPos;

    // Django admin에서 변경 감지를 위해 input 이벤트 발생
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".js-insert-token");
    if (!btn) return;

    const token = btn.getAttribute("data-token");
    if (!token) return;

    // Post의 content textarea 기본 id는 대개 id_content
    const textarea = document.getElementById("id_content");
    if (!textarea) {
      alert("본문 입력창(id_content)을 찾지 못했습니다.");
      return;
    }

    insertAtCursor(textarea, token);
  });
})();
