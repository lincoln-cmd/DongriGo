/*
Board state manager
- Loading overlay + Error overlay
- Single source of truth for:
  - open/close based on markers in #boardContent
  - reading mode
  - close (js-close): close UI + pushState('/') + (optional) load home via HTMX
  - back (js-back): history.back() preferred ONLY when detail was entered via HTMX; otherwise load href
  - mobile dim + swipe close
  - URL sync on popstate (visual only)
*/

(function () {
  'use strict';

  const wrap = document.querySelector('.wrap');
  const board = document.getElementById('board');
  const boardContent = document.getElementById('boardContent');
  const loadingEl = document.getElementById('boardLoading');
  const errorEl = document.getElementById('boardError');
  const retryBtn = document.getElementById('boardRetryBtn');

  const dimEl = document.getElementById('boardDim');
  const edgeEl = document.getElementById('boardSwipeEdge');

  const mm = window.matchMedia('(max-width: 820px)');

  if (!wrap || !board || !boardContent) return;

  let lastUrl = '';

  // --------------------------------
  // Step B support: direct-entry safe back
  // --------------------------------
  const KEY_LAST_LIST_URL   = 'DG:lastListUrl';
  const KEY_LAST_DETAIL_URL = 'DG:lastDetailUrl';
  const KEY_DETAIL_VIA_HTMX = 'DG:detailViaHtmx'; // ✅ 이번 페이지 생애에서 HTMX로 상세 진입했는지

  function safeGet(key) {
    try { return sessionStorage.getItem(key) || ''; } catch (_) { return ''; }
  }
  function safeSet(key, val) {
    try { sessionStorage.setItem(key, val || ''); } catch (_) {}
  }

  function currentPathWithSearch() {
    return (window.location.pathname || '/') + (window.location.search || '');
  }

  function _normUrl(u) {
    try {
      const x = new URL(u, window.location.origin);
      return x.pathname + x.search;
    } catch (_) {
      return u || '';
    }
  }

  // 기대 라우트: /<country>/<category>/<post>/ (세그먼트 3개 이상이면 상세로 간주)
  function _isPostDetailUrl(u) {
    const norm = _normUrl(u);
    const path = (norm.split('?')[0] || '').toString();
    const parts = path.split('/').filter(Boolean);
    return parts.length >= 3;
  }

  function loadHrefIntoBoard(expected) {
    if (window.htmx && typeof window.htmx.ajax === 'function') {
      window.htmx.ajax('GET', expected, { target: '#boardContent', swap: 'innerHTML' });
      try { history.pushState({}, '', expected); } catch (_) {}
    } else {
      window.location.href = expected;
    }
  }

  // 상세로 "진입하는 요청"이면, 그 직전(현재) URL을 리스트로 저장 + 어떤 상세로 갔는지도 저장
  function rememberListIfGoingToDetail(requestUrl) {
    if (!_isPostDetailUrl(requestUrl)) return;

    const cur = currentPathWithSearch(); // 상세로 가기 직전 URL (리스트/탭/검색/페이지)
    const detail = _normUrl(requestUrl);

    safeSet(KEY_LAST_LIST_URL, cur);
    safeSet(KEY_LAST_DETAIL_URL, detail);

    // ✅ "이번 페이지 생애에서 HTMX로 상세 진입" 표시
    safeSet(KEY_DETAIL_VIA_HTMX, '1');
  }

  // --------------------------------
  // overlays
  // --------------------------------
  function setHidden(el, hidden) {
    if (!el) return;
    if (hidden) {
      el.setAttribute('hidden', '');
      el.setAttribute('aria-hidden', 'true');
    } else {
      el.removeAttribute('hidden');
      el.setAttribute('aria-hidden', 'false');
    }
  }

  function showLoading(url) {
    if (url) lastUrl = url;
    setHidden(errorEl, true);
    setHidden(loadingEl, false);
  }

  function hideLoading() {
    setHidden(loadingEl, true);
  }

  function showError(url) {
    if (url) lastUrl = url;
    hideLoading();
    setHidden(errorEl, false);
  }

  function hideError() {
    setHidden(errorEl, true);
  }

  async function retry() {
    const url = lastUrl || currentPathWithSearch();
    if (!url) return;

    if (window.htmx && typeof window.htmx.ajax === 'function') {
      hideError();
      showLoading(url);
      try {
        window.htmx.ajax('GET', url, { target: '#boardContent', swap: 'innerHTML' });
      } catch (_) {
        showError(url);
      }
      return;
    }

    hideError();
    showLoading(url);

    try {
      const res = await fetch(url, {
        method: 'GET',
        headers: { 'HX-Request': 'true', 'X-Requested-With': 'XMLHttpRequest' },
        cache: 'no-store'
      });

      if (!res.ok) throw new Error('HTTP ' + res.status);

      const html = await res.text();
      boardContent.innerHTML = html;

      if (window.htmx && typeof window.htmx.process === 'function') {
        window.htmx.process(boardContent);
      }

      hideLoading();

      const evt = new CustomEvent('htmx:afterSwap', { bubbles: true });
      boardContent.dispatchEvent(evt);

    } catch (_) {
      showError(url);
    }
  }

  // Expose minimal API for globe.js (loading/error)
  window.DongriGoBoardState = {
    startLoading: showLoading,
    stopLoading: hideLoading,
    showError: showError,
    hideError: hideError,
    setLastUrl: (u) => { lastUrl = u || lastUrl; },
    retry: retry,
  };

  if (retryBtn) {
    retryBtn.addEventListener('click', (e) => {
      e.preventDefault();
      retry();
    });
  }

  // -----------------------------
  // UI state (single source)
  // -----------------------------
  function isBoardOpen() {
    return wrap.classList.contains('has-board');
  }

  function hardResetTransforms() {
    board.style.transition = '';
    board.style.transform = '';
    wrap.classList.remove('dragging');
    if (dimEl) dimEl.style.opacity = '';
  }

  function setDim(on) {
    if (!dimEl) return;

    if (!mm.matches) {
      dimEl.classList.remove('on');
      dimEl.style.opacity = '';
      return;
    }

    if (on) dimEl.classList.add('on');
    else {
      dimEl.classList.remove('on');
      dimEl.style.opacity = '';
    }
  }

  function openVisualOnly() {
    if (isBoardOpen()) {
      setDim(true);
      return;
    }
    hardResetTransforms();
    wrap.classList.remove('no-board');
    wrap.classList.add('has-board');
    wrap.dataset.hasBoard = '1';
    setDim(true);
  }

  function closeVisualOnly() {
    if (!isBoardOpen()) {
      setDim(false);
      return;
    }
    hardResetTransforms();
    wrap.classList.add('closing');
    wrap.classList.remove('has-board');
    wrap.classList.add('no-board');
    wrap.dataset.hasBoard = '0';
    setDim(false);
    window.setTimeout(() => wrap.classList.remove('closing'), 260);
  }

  function syncReadingModeFromContent() {
    const marker = boardContent.querySelector("[data-has-post='1']");
    if (marker) board.classList.add('reading');
    else board.classList.remove('reading');
  }

  function syncOpenCloseFromContent() {
    const hasCountry = !!boardContent.querySelector("[data-has-country='1']");
    if (hasCountry) openVisualOnly();
    else closeVisualOnly();
  }

  function syncUiFromContent() {
    syncReadingModeFromContent();
    syncOpenCloseFromContent();
  }

  // -----------------------------
  // HTMX hooks (boardContent only)
  // -----------------------------
  function isBoardRequest(detail) {
    if (!detail) return false;

    const tgt = detail.target;
    if (tgt && tgt.id === 'boardContent') return true;

    const elt = detail.elt;
    if (elt && typeof elt.getAttribute === 'function') {
      const hxTarget = elt.getAttribute('hx-target') || '';
      if (hxTarget === '#boardContent') return true;
    }

    return false;
  }

  function extractUrl(detail) {
    const pi = detail.pathInfo || {};
    return (
      pi.finalRequestPath ||
      pi.requestPath ||
      (detail.requestConfig && detail.requestConfig.path) ||
      (detail.xhr && detail.xhr.responseURL) ||
      ''
    );
  }

  document.body.addEventListener('htmx:beforeRequest', (e) => {
    if (!isBoardRequest(e.detail)) return;

    const url = extractUrl(e.detail);

    // ✅ 리스트→상세 진입 tracking
    rememberListIfGoingToDetail(url);

    showLoading(url);
  });

  document.body.addEventListener('htmx:afterSwap', (e) => {
    if (e.target && e.target.id === 'boardContent') {
      hideLoading();
      hideError();
      syncUiFromContent();

      // ✅ afterSwap 결과가 "상세"면 detailViaHtmx=1 유지,
      // 상세가 아니면(목록/홈) 0으로 내려서 direct-entry 구분을 강화
      const isDetail = !!boardContent.querySelector("[data-has-post='1']");
      safeSet(KEY_DETAIL_VIA_HTMX, isDetail ? '1' : '0');
    }
  });

  document.body.addEventListener('htmx:historyRestore', () => {
    syncUiFromContent();
  });

  function onHtmxError(e) {
    if (!isBoardRequest(e.detail)) return;
    const url = extractUrl(e.detail);
    showError(url);
  }

  document.body.addEventListener('htmx:responseError', onHtmxError);
  document.body.addEventListener('htmx:sendError', onHtmxError);
  document.body.addEventListener('htmx:timeout', onHtmxError);

  // -----------------------------
  // Close / Back actions
  // -----------------------------
  function pushHomeUrl() {
    try {
      if ((window.location.pathname || '/') !== '/') {
        history.pushState({}, '', '/');
      }
    } catch (_) {}
  }

  function abortBoardRequests() {
    try {
      if (window.htmx) window.htmx.trigger(boardContent, 'htmx:abort');
    } catch (_) {}
  }

  function loadHomeIntoBoardContent() {
    if (!window.htmx || typeof window.htmx.ajax !== 'function') return;
    window.htmx.ajax('GET', '/', { target: '#boardContent', swap: 'innerHTML' });
  }

  // ✅ Step A: 닫기 동작 “완전 고정”
  function closeBoard({ loadHome = true } = {}) {
    abortBoardRequests();
    closeVisualOnly();
    pushHomeUrl();
    if (loadHome) loadHomeIntoBoardContent();
  }

  // ✅ Step B: direct-entry면 무조건 href로, HTMX로 들어온 상세에서만 history.back()
  function backSmart(href) {
    const expected = _normUrl(href);
    if (!expected) return;

    const viaHtmx = safeGet(KEY_DETAIL_VIA_HTMX) === '1';
    if (!viaHtmx) {
      // ✅ 직접 URL 진입(풀 페이지 로드) 포함 → history.back() 금지
      loadHrefIntoBoard(expected);
      return;
    }

    // HTMX로 상세 들어온 케이스만 history.back() 시도 + 불일치면 복구
    let checked = false;

    const checkAndFix = () => {
      if (checked) return;
      checked = true;

      const now = currentPathWithSearch();
      if (now === expected) return;

      loadHrefIntoBoard(expected);
    };

    const onPop = () => setTimeout(checkAndFix, 0);
    window.addEventListener('popstate', onPop, { once: true });

    try { history.back(); } catch (_) { checkAndFix(); return; }
    setTimeout(checkAndFix, 500);
  }

  // ✅ 클릭 가로채기: capture 단계에서 htmx보다 먼저 먹고(stopImmediatePropagation)
  document.addEventListener('click', (e) => {
    const a = e.target && e.target.closest ? e.target.closest('a') : null;
    if (!a) return;

    if (a.classList.contains('js-close')) {
      e.preventDefault();
      e.stopPropagation();
      if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();
      closeBoard({ loadHome: true });
      return;
    }

    if (a.classList.contains('js-back')) {
      e.preventDefault();
      e.stopPropagation();
      if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();
      backSmart(a.getAttribute('href') || '');
      return;
    }
  }, true); // ✅ capture=true

  // dim click to close (mobile only)
  if (dimEl) {
    dimEl.addEventListener('click', (e) => {
      if (!mm.matches) return;
      if (!isBoardOpen()) return;
      e.preventDefault();
      closeBoard({ loadHome: true });
    });
  }

  // -----------------------------
  // Swipe close (edge only, mobile)
  // -----------------------------
  function snapTo(x, ms) {
    board.style.transition = `transform ${ms}ms ease`;
    board.style.transform = `translateX(${x}px)`;
    window.setTimeout(() => { board.style.transition = ''; }, ms + 20);
  }

  function snapBack(ms) {
    board.style.transition = `transform ${ms}ms ease`;
    board.style.transform = `translateX(0px)`;
    window.setTimeout(() => {
      board.style.transition = '';
      board.style.transform = '';
    }, ms + 20);
  }

  let startX = 0, startY = 0, lastX = 0;
  let dragging = false;
  let started = false;

  let prevX = 0;
  let prevT = 0;
  let lastV = 0; // px/ms

  function resetDrag() {
    dragging = false;
    started = false;
    wrap.classList.remove('dragging');
    if (dimEl) dimEl.style.opacity = '';
    setDim(true);
    lastV = 0;
  }

  if (edgeEl) {
    edgeEl.addEventListener('pointerdown', (e) => {
      if (!mm.matches) return;
      if (!isBoardOpen()) return;

      started = true;
      dragging = false;

      startX = e.clientX;
      startY = e.clientY;
      lastX = startX;

      const t = performance.now();
      prevX = startX;
      prevT = t;
      lastV = 0;

      setDim(true);
      try { edgeEl.setPointerCapture(e.pointerId); } catch (_) {}
    });

    edgeEl.addEventListener('pointermove', (e) => {
      if (!mm.matches) return;
      if (!started) return;

      const dx = e.clientX - startX;
      const dy = e.clientY - startY;

      if (dx < 0) return;

      if (!dragging) {
        if (Math.abs(dx) < 10) return;
        if (Math.abs(dx) < Math.abs(dy) + 8) return;
        dragging = true;
        wrap.classList.add('dragging');
      }

      e.preventDefault();

      const nowT = performance.now();
      const nowX = e.clientX;
      const dt = Math.max(1, nowT - prevT);
      lastV = (nowX - prevX) / dt;

      prevT = nowT;
      prevX = nowX;

      lastX = nowX;

      const w = board.getBoundingClientRect().width || window.innerWidth;
      const clamped = Math.min(dx, w);
      board.style.transform = `translateX(${clamped}px)`;

      if (dimEl) {
        dimEl.classList.add('on');
        const t = Math.max(0, Math.min(1, clamped / w));
        const opacity = 0.35 * (1 - t);
        dimEl.style.opacity = String(opacity);
      }
    }, { passive: false });

    edgeEl.addEventListener('pointerup', () => {
      if (!mm.matches) return;
      if (!started) return;

      const dx = lastX - startX;
      const w = board.getBoundingClientRect().width || window.innerWidth;

      const byDistance = dragging && dx > w * 0.25;
      const byVelocity = dragging && dx > 30 && lastV > 1.1;

      if (byDistance || byVelocity) {
        if (dimEl) {
          dimEl.classList.add('on');
          dimEl.style.opacity = '0';
        }
        snapTo(w, 160);
        window.setTimeout(() => closeBoard({ loadHome: true }), 170);
        return;
      }

      snapBack(180);
      window.setTimeout(() => resetDrag(), 190);
    });

    edgeEl.addEventListener('pointercancel', () => {
      if (!mm.matches) return;
      if (!started) return;
      snapBack(180);
      window.setTimeout(() => resetDrag(), 190);
    });
  }

  // -----------------------------
  // popstate: visual sync only
  // -----------------------------
  function isHomePath() {
    const p = window.location.pathname || '/';
    return p === '/';
  }

  window.addEventListener('popstate', () => {
    if (isHomePath()) closeVisualOnly();
  });

  document.addEventListener('DOMContentLoaded', () => {
    // ✅ 핵심: "풀 페이지 로드"가 발생하면 detailViaHtmx는 무조건 0에서 시작해야 함
    safeSet(KEY_DETAIL_VIA_HTMX, '0');
    syncUiFromContent();
  });

})();
