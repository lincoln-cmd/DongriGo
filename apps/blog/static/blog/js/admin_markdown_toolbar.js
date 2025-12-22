(function () {
  "use strict";

  function isPostChangeForm() {
    const path = window.location.pathname || "";
    return /\/admin\/.+\/post\/(add|\d+\/change)\/?$/.test(path);
  }

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function debounce(fn, ms) {
    let t = null;
    return function (...args) {
      if (t) clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  function insertAround(textarea, before, after, defaultText) {
    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;

    const value = textarea.value || "";
    const selected = value.slice(start, end) || defaultText || "";

    const next = value.slice(0, start) + before + selected + after + value.slice(end);
    textarea.value = next;

    const newStart = start + before.length;
    const newEnd = newStart + selected.length;
    textarea.focus();
    textarea.setSelectionRange(newStart, newEnd);

    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function insertLinePrefix(textarea, prefix) {
    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;
    const value = textarea.value || "";

    const beforeText = value.slice(0, start);
    const sel = value.slice(start, end);
    const afterText = value.slice(end);

    if (!sel) {
      const lineStart = beforeText.lastIndexOf("\n") + 1;
      textarea.value = value.slice(0, lineStart) + prefix + value.slice(lineStart);
      const pos = start + prefix.length;
      textarea.focus();
      textarea.setSelectionRange(pos, pos);
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }

    const lines = sel.split("\n").map((ln) => (ln ? prefix + ln : ln));
    const replaced = lines.join("\n");
    textarea.value = beforeText + replaced + afterText;

    textarea.focus();
    textarea.setSelectionRange(start, start + replaced.length);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  // ✅ Django admin 레이아웃에서 content 필드의 “필드 컨테이너”를 안정적으로 찾기
  function findContentFieldContainer(textarea) {
    // 보통은 .form-row 또는 .field-content가 있음
    return (
      textarea.closest(".form-row") ||
      textarea.closest(".field-content") ||
      textarea.closest(".fieldBox") ||
      textarea.parentElement
    );
  }

  function ensureToolbar(textarea) {
    if (qs(".js-md-toolbar")) return;

    const container = findContentFieldContainer(textarea);
    if (!container) return;

    // 툴바를 “textarea 바로 위”에 넣기 위한 앵커
    // (옆으로 붙는 문제를 피하려고) textarea를 감싸는 wrapper를 하나 만든다.
    // wrapper는 block 레이아웃으로 강제.
    let wrap = textarea.closest(".js-md-wrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.className = "js-md-wrap";
      wrap.style.display = "block";
      wrap.style.width = "100%";

      // textarea를 wrap으로 감싼다.
      textarea.parentNode.insertBefore(wrap, textarea);
      wrap.appendChild(textarea);
    }

    const bar = document.createElement("div");
    bar.className = "js-md-toolbar";
    bar.style.display = "flex";
    bar.style.flexWrap = "wrap";
    bar.style.gap = "6px";
    bar.style.margin = "0 0 8px 0";
    bar.style.alignItems = "center";

    function btn(label, title, onClick) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "button";
      b.textContent = label;
      b.title = title;
      b.addEventListener("click", (e) => {
        e.preventDefault();
        onClick();
      });
      bar.appendChild(b);
      return b;
    }

    btn("B", "굵게", () => insertAround(textarea, "**", "**", "굵게"));
    btn("I", "기울임", () => insertAround(textarea, "*", "*", "기울임"));
    btn("H2", "헤딩(##)", () => insertLinePrefix(textarea, "## "));
    btn("H3", "헤딩(###)", () => insertLinePrefix(textarea, "### "));
    btn("Link", "링크", () => insertAround(textarea, "[", "](https://)", "텍스트"));
    btn("Code", "인라인 코드", () => insertAround(textarea, "`", "`", "code"));
    btn("Block", "코드 블록", () => insertAround(textarea, "\n```text\n", "\n```\n", "code here"));
    btn("---", "구분선", () => insertAround(textarea, "\n---\n", "", ""));

    // ✅ 핵심: wrap(=textarea 상단)에 bar를 넣는다.
    wrap.insertBefore(bar, textarea);
  }

  function main() {
    if (!isPostChangeForm()) return;

    const textarea = qs("#id_content");
    if (!textarea) return;

    ensureToolbar(textarea);

    // (선택) textarea 리사이즈/레이아웃 변화가 있으면 한번 더 보정
    const fix = debounce(() => ensureToolbar(textarea), 200);
    window.addEventListener("resize", fix, { passive: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", main);
  } else {
    main();
  }
})();
