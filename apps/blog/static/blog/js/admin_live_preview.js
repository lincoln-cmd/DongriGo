(function () {
  "use strict";

  function isPostChangeForm() {
    const path = window.location.pathname || "";
    // /admin/apps.blog/post/add/
    // /admin/apps.blog/post/23/change/
    return /\/admin\/.+\/post\/(add|\d+\/change)\/?$/.test(path);
  }

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function getCsrfToken() {
    const el = qs('input[name="csrfmiddlewaretoken"]');
    return el ? el.value : "";
  }

  function getPostIdFromUrl() {
    const m = (window.location.pathname || "").match(/\/admin\/.+\/post\/(\d+)\/change\/?$/);
    return m ? m[1] : "";
  }

  function ensurePreviewUI() {
    const content = qs("#id_content");
    if (!content) return null;

    const field =
      content.closest(".form-row") ||
      content.closest(".field-content") ||
      content.parentElement;

    if (!field) return null;

    let wrap = qs(".js-live-preview-wrap");
    if (wrap) return { content, wrap };

    wrap = document.createElement("div");
    wrap.className = "js-live-preview-wrap";
    wrap.style.marginTop = "12px";
    wrap.style.padding = "10px";
    wrap.style.border = "1px solid #ddd";
    wrap.style.borderRadius = "10px";

    const top = document.createElement("div");
    top.style.display = "flex";
    top.style.gap = "10px";
    top.style.alignItems = "center";
    top.style.marginBottom = "10px";

    const title = document.createElement("strong");
    title.textContent = "라이브 미리보기";
    title.style.fontSize = "13px";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "button js-live-preview-btn";
    btn.textContent = "미리보기 업데이트";

    const hint = document.createElement("span");
    hint.style.fontSize = "12px";
    hint.style.opacity = "0.75";
    hint.textContent = "서버 렌더 결과 기준(수정 화면에서는 [[img:ID]]도 반영됨).";

    top.appendChild(title);
    top.appendChild(btn);
    top.appendChild(hint);

    const box = document.createElement("div");
    box.className = "js-live-preview-box";
    box.style.maxHeight = "340px";
    box.style.overflow = "auto";
    box.style.padding = "12px";
    box.style.border = "1px solid #eee";
    box.style.borderRadius = "10px";
    box.innerHTML = '<div style="opacity:.7">여기에 미리보기가 표시됩니다.</div>';

    wrap.appendChild(top);
    wrap.appendChild(box);

    field.appendChild(wrap);

    return { content, wrap };
  }

  async function fetchPreview(contentValue) {
    const csrf = getCsrfToken();
    const postId = getPostIdFromUrl();

    const body = new URLSearchParams();
    body.set("csrfmiddlewaretoken", csrf);
    body.set("content", contentValue || "");
    if (postId) body.set("post_id", postId);

    const res = await fetch("/__admin/preview/", {
      method: "POST",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      body,
      credentials: "same-origin",
      cache: "no-store",
    });

    if (!res.ok) throw new Error("preview request failed: " + res.status);
    return await res.text();
  }

  function debounce(fn, ms) {
    let t = null;
    return function (...args) {
      if (t) clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  function main() {
    if (!isPostChangeForm()) return;

    const ui = ensurePreviewUI();
    if (!ui) return;

    const content = ui.content;
    const box = qs(".js-live-preview-box", ui.wrap);
    const btn = qs(".js-live-preview-btn", ui.wrap);
    if (!box || !btn) return;

    const render = async () => {
      btn.disabled = true;
      const old = btn.textContent;
      btn.textContent = "미리보기 생성 중...";
      try {
        const html = await fetchPreview(content.value);
        box.innerHTML = html || '<div style="opacity:.7">내용이 비어있습니다.</div>';
      } catch (e) {
        box.innerHTML = '<div style="color:#b00">미리보기 실패. (서버 로그/네트워크 확인)</div>';
      } finally {
        btn.disabled = false;
        btn.textContent = old;
      }
    };

    btn.addEventListener("click", render);

    const auto = debounce(render, 600);
    content.addEventListener("input", auto);

    // 수정 화면에서는 첫 로드 시 1회 렌더(있으면)
    if ((content.value || "").trim()) render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", main);
  } else {
    main();
  }
})();
