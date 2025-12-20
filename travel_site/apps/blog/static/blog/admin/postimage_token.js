(function () {
  function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    // fallback
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "-9999px";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      document.execCommand("copy");
      return Promise.resolve();
    } catch (e) {
      return Promise.reject(e);
    } finally {
      document.body.removeChild(ta);
    }
  }

  function insertAtCursor(el, text) {
    // textarea 전용
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    const before = el.value.slice(0, start);
    const after = el.value.slice(end);

    // 토큰이 문장에 붙지 않도록 앞/뒤에 개행을 살짝 보정(취향)
    const prefix = before && !before.endsWith("\n") ? "\n" : "";
    const suffix = after && !after.startsWith("\n") ? "\n" : "";

    el.value = before + prefix + text + suffix + after;

    const pos = (before + prefix + text + suffix).length;
    el.focus();
    el.setSelectionRange(pos, pos);

    // Django admin에서 변경 감지
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function getContentField() {
    // Post 모델의 content 필드 id가 보통 id_content
    return document.getElementById("id_content");
  }

  document.addEventListener("click", async (e) => {
    const copyBtn = e.target.closest(".js-copy-token");
    const insertBtn = e.target.closest(".js-insert-token");
    if (!copyBtn && !insertBtn) return;

    const btn = copyBtn || insertBtn;
    const token = btn.getAttribute("data-token");
    if (!token) return;

    // 복사 버튼: 복사만
    if (copyBtn) {
      try {
        await copyToClipboard(token);
        // 조용히 UX: 버튼 텍스트 잠깐 변경
        const old = copyBtn.textContent;
        copyBtn.textContent = "복사됨";
        setTimeout(() => (copyBtn.textContent = old), 800);
      } catch {
        alert("클립보드 복사에 실패했습니다. 수동으로 복사해주세요: " + token);
      }
      return;
    }

    // 삽입 버튼: (복사 + 본문 삽입) 둘 다 해주면 편함
    const content = getContentField();
    if (!content) {
      alert("본문 입력칸(id_content)을 찾지 못했습니다. content 필드 id를 확인해주세요.");
      return;
    }

    try {
      await copyToClipboard(token);
    } catch {
      // 복사 실패해도 삽입은 진행
    }

    insertAtCursor(content, token);

    const old = insertBtn.textContent;
    insertBtn.textContent = "삽입됨";
    setTimeout(() => (insertBtn.textContent = old), 800);
  });
})();
