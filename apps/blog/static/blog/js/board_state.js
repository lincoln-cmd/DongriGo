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

[2026-01] Patch:
- Allow "board-open" screens that are NOT country-based (e.g. /tags/)
  => open board when:
     1) data-has-country="1" OR
     2) data-board-open="1" OR
     3) location path is /tags or /tags/<slug> (fallback when marker missing)
*/

(function () {
  'use strict';

  const wrap = document.querySelector('.wrap');
  const board = document.getElementById('board');
  const boardContent = document.getElementById('boardContent');

  const loadingEl = document.getElementById('boardLoading');
  const errorEl = document.getElementById('boardError');
  const retryBtn = document.getElementById('boardRetryBtn');

  // (optional) richer error UI elements (if exist)
  const errorMsgEl = document.getElementById('boardErrorMsg');
  const errorMetaEl = document.getElementById('boardErrorMeta');

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
  const KEY_DETAIL_VIA_HTMX = 'DG:detailViaHtmx';

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

  function rememberListIfGoingToDetail(requestUrl) {
    if (!_isPostDetailUrl(requestUrl)) return;

    const cur = currentPathWithSearch();
    const detail = _normUrl(requestUrl);

    safeSet(KEY_LAST_LIST_URL, cur);
    safeSet(KEY_LAST_DETAIL_URL, detail);

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

  function setErrorMessage({ url, status }) {
    if (!errorMsgEl && !errorMetaEl) return;

    const offline = (typeof navigator !== 'undefined' && navigator.onLine === false);

    if (errorMsgEl) {
      if (offline) {
        errorMsgEl.textContent = '인터넷 연결이 끊겼습니다. 연결 상태를 확인해 주세요.';
      } else if (status && status !== 0) {
        errorMsgEl.textContent = '서버 오류로 요청이 실패했습니다. 잠시 후 다시 시도해 주세요.';
      } else {
        errorMsgEl.textContent = '네트워크 또는 서버 오류로 요청이 실패했습니다.';
      }
    }

    if (errorMetaEl) {
      const parts = [];
      if (offline) parts.push('offline');
      if (status && status !== 0) parts.push(`HTTP ${status}`);
      if (url) parts.push(_normUrl(url));
      const txt = parts.join(' · ');
      if (txt) {
        errorMetaEl.textContent = txt;
        errorMetaEl.removeAttribute('aria-hidden');
      } else {
        errorMetaEl.textContent = '';
        errorMetaEl.setAttribute('aria-hidden', 'true');
      }
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

  function showError(url, meta = {}) {
    if (url) lastUrl = url;
    hideLoading();
    setErrorMessage({ url, status: meta.status || 0 });
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
        showError(url, { status: 0 });
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
      showError(url, { status: 0 });
    }
  }

  // Expose minimal API for globe.js (loading/error)
  window.DongriGoBoardState = {
    startLoading: showLoading,
    stopLoading: hideLoading,
    showError: (url, meta) => showError(url, meta || {}),
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

  function isTagsPathFromLocation() {
    const p = (window.location.pathname || '/').toString();
    // /tags/ , /tags/<slug>/ ... (fallback if template marker missing)
    return /^\/tags(\/|$)/.test(p);
  }

  function shouldBoardBeOpenFromContentOrUrl() {
    const hasCountry = !!boardContent.querySelector("[data-has-country='1']");
    if (hasCountry) return true;

    // ✅ Legacy/compat marker: tags board can announce itself
    const hasTags = !!boardContent.querySelector("[data-has-tags='1']");
    if (hasTags) return true;

    // ✅ New marker: non-country boards (tags etc.)
    const boardOpen = !!boardContent.querySelector("[data-board-open='1']");
    if (boardOpen) return true;

    // ✅ Fallback by URL for /tags/ (prevents “request succeeds but board stays closed”)
    if (isTagsPathFromLocation()) return true;

    return false;
  }

  function syncOpenCloseFromContent() {
    if (shouldBoardBeOpenFromContentOrUrl()) openVisualOnly();
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
    rememberListIfGoingToDetail(url);

    // ✅ If requesting something other than '/', open board immediately to avoid "nothing happens" feeling
    const norm = _normUrl(url);
    if (norm && norm !== '/' && norm !== '/?') {
      openVisualOnly();
    }

    showLoading(url);
  });

  document.body.addEventListener('htmx:afterSwap', (e) => {
    if (e.target && e.target.id === 'boardContent') {
      hideLoading();
      hideError();
      syncUiFromContent();

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

    // ✅ If error occurred while loading non-home content, keep board open so error overlay is visible
    const norm = _normUrl(url);
    if (norm && norm !== '/' && norm !== '/?') {
      openVisualOnly();
    }

    showError(url, { status: 0 });
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

  function closeBoard({ loadHome = true } = {}) {
    abortBoardRequests();
    closeVisualOnly();
    pushHomeUrl();
    if (loadHome) loadHomeIntoBoardContent();
  }

  function backSmart(href) {
    const expected = _normUrl(href);
    if (!expected) return;

    const viaHtmx = safeGet(KEY_DETAIL_VIA_HTMX) === '1';
    if (!viaHtmx) {
      loadHrefIntoBoard(expected);
      return;
    }

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
  }, true);

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
        const t2 = Math.max(0, Math.min(1, clamped / w));
        const opacity = 0.35 * (1 - t2);
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
    // ✅ DO NOT load content here (stability rule)
    if (isHomePath()) {
      closeVisualOnly();
      return;
    }

    // ✅ For /tags/... ensure board is visible even if marker missing
    if (isTagsPathFromLocation()) {
      openVisualOnly();
      return;
    }

    // otherwise, rely on content markers
    syncUiFromContent();
  });

  document.addEventListener('DOMContentLoaded', () => {
    // 풀 페이지 로드 시작점에서는 "HTMX 상세 진입"을 0으로 초기화
    safeSet(KEY_DETAIL_VIA_HTMX, '0');
    syncUiFromContent();
  });

})();
