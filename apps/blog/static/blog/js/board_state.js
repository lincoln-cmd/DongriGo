(function () {
  'use strict';

  const wrap = document.querySelector('.wrap');
  const board = document.getElementById('board');
  const boardContent = document.getElementById('boardContent');
  const loadingEl = document.getElementById('boardLoading');
  const errorEl = document.getElementById('boardError');
  const retryBtn = document.getElementById('boardRetryBtn');

  const errorMsgEl = document.getElementById('boardErrorMsg');
  const errorMetaEl = document.getElementById('boardErrorMeta');

  const dimEl = document.getElementById('boardDim');
  const edgeEl = document.getElementById('boardSwipeEdge');

  const mm = window.matchMedia('(max-width: 820px)');

  if (!wrap || !board || !boardContent) return;

  let lastUrl = '';
  let autoRetryArmed = false;

  const KEY_LAST_LIST_URL   = 'DG:lastListUrl';
  const KEY_LAST_DETAIL_URL = 'DG:lastDetailUrl';
  const KEY_DETAIL_VIA_HTMX = 'DG:detailViaHtmx';

  const KEY_LAST_BOARD_URL      = 'DG:lastBoardUrl';
  const KEY_LAST_GOOD_BOARD_URL = 'DG:lastGoodBoardUrl';

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

  function setText(el, text) {
    if (!el) return;
    el.textContent = text || '';
  }

  function setDisabled(el, disabled) {
    if (!el) return;
    if (disabled) el.setAttribute('disabled', '');
    else el.removeAttribute('disabled');
  }

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

  function ensureBoardVisible() {
    openVisualOnly();
  }

  function renderErrorMessage(url, info) {
    const online = (typeof navigator !== 'undefined') ? navigator.onLine : true;
    const status = info && typeof info.status === 'number' ? info.status : 0;

    if (!online) {
      setText(errorMsgEl, '인터넷 연결이 끊겼습니다. 연결 상태를 확인해 주세요.');
      setText(errorMetaEl, '온라인 상태로 전환되면 자동으로 1회 재시도합니다.');
      setDisabled(retryBtn, true);
      return;
    }

    setDisabled(retryBtn, false);

    if (status === 404) {
      setText(errorMsgEl, '요청한 콘텐츠를 찾을 수 없습니다.');
      setText(errorMetaEl, `HTTP ${status} · ${_normUrl(url)}`);
      return;
    }

    if (status >= 500) {
      setText(errorMsgEl, '서버 오류로 요청이 실패했습니다. 잠시 후 다시 시도해 주세요.');
      setText(errorMetaEl, `HTTP ${status} · ${_normUrl(url)}`);
      return;
    }

    if (status === 0) {
      setText(errorMsgEl, '네트워크 또는 서버 오류로 요청이 실패했습니다.');
      setText(errorMetaEl, _normUrl(url));
      return;
    }

    setText(errorMsgEl, '요청이 실패했습니다. 다시 시도해 주세요.');
    setText(errorMetaEl, `HTTP ${status} · ${_normUrl(url)}`);
  }

  function showLoading(url) {
    if (url) {
      lastUrl = url;
      safeSet(KEY_LAST_BOARD_URL, _normUrl(url));
    }
    ensureBoardVisible();
    setHidden(errorEl, true);
    setHidden(loadingEl, false);
  }

  function hideLoading() {
    setHidden(loadingEl, true);
  }

  function showError(url, info) {
    const u = url || lastUrl || safeGet(KEY_LAST_BOARD_URL) || currentPathWithSearch();
    lastUrl = u;
    safeSet(KEY_LAST_BOARD_URL, _normUrl(u));

    ensureBoardVisible();

    hideLoading();
    renderErrorMessage(u, info || {});
    setHidden(errorEl, false);

    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      autoRetryArmed = true;
    }
  }

  function hideError() {
    setHidden(errorEl, true);
    setDisabled(retryBtn, false);
    setText(errorMetaEl, '');
  }

  async function retry() {
    const url =
      lastUrl ||
      safeGet(KEY_LAST_BOARD_URL) ||
      currentPathWithSearch();

    if (!url) return;

    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      showError(url, { status: 0 });
      return;
    }

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

    } catch (e) {
      const msg = (e && e.message) ? e.message : '';
      const m = msg.match(/HTTP\s+(\d+)/i);
      const status = m ? parseInt(m[1], 10) : 0;
      showError(url, { status: Number.isFinite(status) ? status : 0 });
    }
  }

  window.DongriGoBoardState = {
    startLoading: showLoading,
    stopLoading: hideLoading,
    showError: showError,
    hideError: hideError,
    setLastUrl: (u) => { lastUrl = u || lastUrl; safeSet(KEY_LAST_BOARD_URL, _normUrl(lastUrl)); },
    retry: retry,
  };

  if (retryBtn) {
    retryBtn.addEventListener('click', (e) => {
      e.preventDefault();
      retry();
    });
  }

  window.addEventListener('online', () => {
    setDisabled(retryBtn, false);

    const isErrorVisible = errorEl && !errorEl.hasAttribute('hidden');
    if (!isErrorVisible) return;
    if (!autoRetryArmed) return;

    autoRetryArmed = false;
    retry();
  });

  window.addEventListener('offline', () => {
    const isErrorVisible = errorEl && !errorEl.hasAttribute('hidden');
    if (!isErrorVisible) return;
    showError(lastUrl || safeGet(KEY_LAST_BOARD_URL) || currentPathWithSearch(), { status: 0 });
  });

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

    // ✅ 핵심: 오프라인이면 HTMX 요청 자체를 취소해야 Network에 실패 XHR이 안 뜸
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      try { e.preventDefault(); } catch (_) {}
      showError(url, { status: 0 });
      return;
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

      safeSet(KEY_LAST_GOOD_BOARD_URL, currentPathWithSearch());
      safeSet(KEY_LAST_BOARD_URL, currentPathWithSearch());
      lastUrl = currentPathWithSearch();
    }
  });

  document.body.addEventListener('htmx:historyRestore', () => {
    syncUiFromContent();
  });

  function onHtmxError(e) {
    if (!isBoardRequest(e.detail)) return;

    const url = extractUrl(e.detail);
    const xhr = e.detail && e.detail.xhr ? e.detail.xhr : null;
    const status = xhr && typeof xhr.status === 'number' ? xhr.status : 0;

    showError(url, { status });
  }

  document.body.addEventListener('htmx:responseError', onHtmxError);
  document.body.addEventListener('htmx:sendError', onHtmxError);
  document.body.addEventListener('htmx:timeout', onHtmxError);

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

  if (dimEl) {
    dimEl.addEventListener('click', (e) => {
      if (!mm.matches) return;
      if (!isBoardOpen()) return;
      e.preventDefault();
      closeBoard({ loadHome: true });
    });
  }

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
  let lastV = 0;

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

  function isHomePath() {
    const p = window.location.pathname || '/';
    return p === '/';
  }

  window.addEventListener('popstate', () => {
    if (isHomePath()) closeVisualOnly();
  });

  document.addEventListener('DOMContentLoaded', () => {
    safeSet(KEY_DETAIL_VIA_HTMX, '0');
    syncUiFromContent();

    const cur = currentPathWithSearch();
    safeSet(KEY_LAST_BOARD_URL, cur);
    lastUrl = cur;
  });

})();
