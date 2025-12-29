// search_ux.js
// Phase 2-5:
// - LEFT(country) search: ArrowUp/Down + Enter navigation + Esc clear
// - RIGHT(board) search: recent queries (localStorage) + dropdown + keyboard nav
// - HTMX swap 대응: #boardContent가 바뀌면 재바인딩

(function () {
  "use strict";

  const RECENT_KEY = "dongrigo_recent_searches_v1";
  const RECENT_MAX = 8;

  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function readRecent() {
    try {
      const raw = localStorage.getItem(RECENT_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr.filter(Boolean) : [];
    } catch {
      return [];
    }
  }

  function writeRecent(arr) {
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify(arr));
    } catch { /* ignore */ }
  }

  function addRecent(q) {
    const v = (q || "").trim();
    if (!v) return;
    const cur = readRecent();
    const next = [v, ...cur.filter(x => x !== v)].slice(0, RECENT_MAX);
    writeRecent(next);
  }

  function clearRecent() {
    try { localStorage.removeItem(RECENT_KEY); } catch { /* ignore */ }
  }

  // ------------------------------------------------------------
  // LEFT: Country search keyboard UX
  // ------------------------------------------------------------
  function bindCountrySearch() {
    const input = qs("#countrySearch");
    const list = qs("#countryList");
    if (!input || !list) return;

    const links = qsa("a.country-link", list);
    if (!links.length) return;

    let activeIdx = -1;

    function visibleLinks() {
      return links.filter(a => a.style.display !== "none");
    }

    function clearActive() {
      links.forEach(a => a.classList.remove("kbd-active"));
      activeIdx = -1;
    }

    function setActiveByIndex(i) {
      const vis = visibleLinks();
      if (!vis.length) { clearActive(); return; }

      const safe = Math.max(0, Math.min(i, vis.length - 1));
      links.forEach(a => a.classList.remove("kbd-active"));
      vis[safe].classList.add("kbd-active");
      activeIdx = links.indexOf(vis[safe]);

      // 스크롤 보정(드롭다운 내부)
      if (vis[safe].scrollIntoView) {
        vis[safe].scrollIntoView({ block: "nearest" });
      }
    }

    function filter() {
      const q = input.value.trim().toLowerCase();
      list.classList.toggle("has-query", q.length > 0);

      links.forEach(a => {
        const name = (a.textContent || "").trim().toLowerCase();
        a.style.display = name.includes(q) ? "" : "none";
      });

      // 필터 결과가 바뀌면 첫 항목을 활성화(있으면)
      const vis = visibleLinks();
      if (vis.length) setActiveByIndex(0);
      else clearActive();
    }

    input.addEventListener("input", filter);

    input.addEventListener("keydown", (e) => {
      const vis = visibleLinks();

      if (e.key === "Escape") {
        input.value = "";
        filter();
        input.blur();
        return;
      }

      if (!vis.length) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        const curVisIndex = Math.max(0, vis.indexOf(links[activeIdx]));
        setActiveByIndex(curVisIndex + 1);
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        const curVisIndex = Math.max(0, vis.indexOf(links[activeIdx]));
        setActiveByIndex(curVisIndex - 1);
      }

      if (e.key === "Enter") {
        // 활성 항목이 있으면 그 국가로 이동
        const target = links[activeIdx] || vis[0];
        if (target && target.href) {
          e.preventDefault();
          window.location.href = target.href;
        }
      }
    });

    // 초기 상태 반영
    filter();
  }

  // ------------------------------------------------------------
  // RIGHT: Board search recent dropdown
  // ------------------------------------------------------------
  function bindBoardSearch() {
    const boardContent = qs("#boardContent");
    if (!boardContent) return;

    const wrap = qs(".board-search-wrap", boardContent);
    if (!wrap) return;

    const form = qs("form.search", wrap);
    const input = qs("input.search-input[name='q']", wrap);
    const page = qs("input[name='page']", wrap);

    const suggest = qs("[data-search-suggest]", wrap);
    const listEl = qs("[data-search-list]", wrap);
    const clearBtn = qs("[data-search-clear]", wrap);

    if (!form || !input || !suggest || !listEl) return;

    let sugIdx = -1;

    function hideSuggest() {
      suggest.hidden = true;
      suggest.setAttribute("aria-hidden", "true");
      sugIdx = -1;
      qsa(".search-suggest__item", listEl).forEach(x => x.classList.remove("is-active"));
    }

    function showSuggest() {
      const items = readRecent();
      if (!items.length) { hideSuggest(); return; }
      suggest.hidden = false;
      suggest.setAttribute("aria-hidden", "false");
    }

    function renderSuggest() {
      const items = readRecent();
      listEl.innerHTML = "";

      if (!items.length) {
        hideSuggest();
        return;
      }

      items.forEach((q, i) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "search-suggest__item";
        btn.dataset.index = String(i);
        btn.textContent = q;

        btn.addEventListener("click", (e) => {
          e.preventDefault();
          input.value = q;
          if (page) page.value = "1";
          hideSuggest();
          // HTMX submit
          if (window.htmx) window.htmx.trigger(form, "submit");
          else form.requestSubmit();
        });

        listEl.appendChild(btn);
      });

      sugIdx = -1;
    }

    function setSugActive(i) {
      const nodes = qsa(".search-suggest__item", listEl);
      if (!nodes.length) return;

      const safe = Math.max(0, Math.min(i, nodes.length - 1));
      nodes.forEach(n => n.classList.remove("is-active"));
      nodes[safe].classList.add("is-active");
      sugIdx = safe;

      if (nodes[safe].scrollIntoView) {
        nodes[safe].scrollIntoView({ block: "nearest" });
      }
    }

    // Focus 시 표시
    input.addEventListener("focus", () => {
      renderSuggest();
      showSuggest();
    });

    // Blur 시 바로 숨기면 클릭이 안 먹을 수 있어 약간 지연
    input.addEventListener("blur", () => {
      setTimeout(() => hideSuggest(), 120);
    });

    // 키보드로 recent 선택
    input.addEventListener("keydown", (e) => {
      const nodes = qsa(".search-suggest__item", listEl);

      if (e.key === "Escape") {
        hideSuggest();
        return;
      }

      // 드롭다운 없으면 무시
      if (suggest.hidden || !nodes.length) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSugActive(sugIdx < 0 ? 0 : sugIdx + 1);
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSugActive(sugIdx < 0 ? 0 : sugIdx - 1);
      }

      if (e.key === "Enter") {
        // 기본 검색도 살려야 해서: suggestion이 활성화된 경우에만 가로채기
        if (sugIdx >= 0 && nodes[sugIdx]) {
          e.preventDefault();
          nodes[sugIdx].click();
        }
      }
    });

    // 검색 submit 시 recent 저장
    form.addEventListener("submit", () => {
      const q = (input.value || "").trim();
      if (!q) return;
      addRecent(q);
      if (page) page.value = "1";
    });

    // clear
    if (clearBtn) {
      clearBtn.addEventListener("click", (e) => {
        e.preventDefault();
        clearRecent();
        renderSuggest();
        hideSuggest();
      });
    }

    // 검색어가 이미 있는 화면에서는 기본 숨김
    hideSuggest();
  }

  function init() {
    bindCountrySearch();
    bindBoardSearch();

    document.body.addEventListener("htmx:afterSwap", (e) => {
      if (e.target && e.target.id === "boardContent") {
        bindBoardSearch();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
