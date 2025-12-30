/*
Board state manager
- Loading overlay + Error overlay
- Single source of truth for:
  - open/close based on markers in #boardContent
  - reading mode
  - close (js-close): close UI + pushState('/') + (optional) load home via HTMX
  - back (js-back): history.back() preferred, fallback to HTMX GET href
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
  let closingToHome = false;

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
    const url = lastUrl || window.location.pathname + window.location.search;
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
    // 닫기 직후 '/'로 밀어놓은 상태에서 늦게 도착한 swap이 보드를 다시 여는 걸 방지
    if ((window.location.pathname || '/') === '/') {
      closingToHome = false;
    }
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
    showLoading(url);
  });

  document.body.addEventListener('htmx:afterSwap', (e) => {
    if (e.target && e.target.id === 'boardContent') {
      hideLoading();
      hideError();
      syncUiFromContent();
    }
  });

  document.body.addEventListener('htmx:historyRestore', () => {
    // historyRestore는 swap 이후 발생하는 경우가 많지만,
    // 보수적으로 한 번 더 동기화
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
    // HTMX에 진행 중 요청이 있으면, target 쪽에서 abort 트리거
    try {
      if (window.htmx) window.htmx.trigger(boardContent, 'htmx:abort');
    } catch (_) {}
  }

  function loadHomeIntoBoardContent() {
    if (!window.htmx || typeof window.htmx.ajax !== 'function') return;
    // URL은 이미 pushState('/') 했으므로 push-url은 false로 둠(중복 방지)
    window.htmx.ajax('GET', '/', { target: '#boardContent', swap: 'innerHTML' });
  }

  function closeBoard({ loadHome = true } = {}) {
    closingToHome = true;
    abortBoardRequests();
    closeVisualOnly();
    pushHomeUrl();
    if (loadHome) loadHomeIntoBoardContent();
  }

  function backWithFallback(href) {
    const before = window.location.href;
    try {
      history.back();
    } catch (_) {}

    window.setTimeout(() => {
      const after = window.location.href;
      if (after !== before) return; // 정상적으로 뒤로 감

      if (href && window.htmx && typeof window.htmx.ajax === 'function') {
        window.htmx.ajax('GET', href, { target: '#boardContent', swap: 'innerHTML' });
      }
    }, 320);
  }

  document.addEventListener('click', (e) => {
    const a = e.target && e.target.closest ? e.target.closest('a') : null;
    if (!a) return;

    if (a.classList.contains('js-close')) {
      e.preventDefault();
      closeBoard({ loadHome: true });
      return;
    }

    function _normUrl(u) {
      try {
        const x = new URL(u, window.location.origin);
        return x.pathname + x.search;
      } catch (_) {
        return u || '';
      }
    }
    
    function backSmart(href) {
      const expected = _normUrl(href);
      if (!expected) return;
    
      let checked = false;
    
      const checkAndFix = () => {
        if (checked) return;
        checked = true;
    
        const now = (window.location.pathname || '') + (window.location.search || '');
        if (now === expected) return; // 정상적으로 기대 목록으로 돌아감
    
        // 기대 목록이 아니면(=travel로 갔거나, 그대로거나) href로 강제 복귀
        if (window.htmx && typeof window.htmx.ajax === 'function') {
          window.htmx.ajax('GET', expected, { target: '#boardContent', swap: 'innerHTML' });
          // URL도 기대값으로 맞춰줌(중요)
          try { history.pushState({}, '', expected); } catch (_) {}
        } else {
          window.location.href = expected;
        }
      };
    
      // popstate가 오면 그 다음 틱에서 검사
      const onPop = () => setTimeout(checkAndFix, 0);
      window.addEventListener('popstate', onPop, { once: true });
    
      try {
        history.back();
      } catch (_) {
        // history.back 자체가 실패하면 바로 href로
        checkAndFix();
        return;
      }
    
      // popstate가 안 오거나(히스토리 없음), restore가 늦는 경우 대비 타임아웃 안전장치
      setTimeout(checkAndFix, 500);
    }
    
    document.addEventListener('click', (e) => {
      const a = e.target && e.target.closest ? e.target.closest('a') : null;
      if (!a) return;
    
      if (a.classList.contains('js-back')) {
        e.preventDefault();
        backSmart(a.getAttribute('href') || '');
        return;
      }
    
      // (js-close 등 다른 핸들러는 기존대로)
    });    
  });

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
  // (content restore is handled by htmx history)
  // -----------------------------
  function isHomePath() {
    const p = window.location.pathname || '/';
    return p === '/';
  }

  window.addEventListener('popstate', () => {
    // 홈으로 돌아간 경우 즉시 닫아 flicker 줄이기
    if (isHomePath()) closeVisualOnly();
  });

  document.addEventListener('DOMContentLoaded', () => {
    // SSR 초기 상태 동기화 (마커 기반)
    syncUiFromContent();
  });

})();
