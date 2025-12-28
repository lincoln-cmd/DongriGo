/*
Board state manager
- Covers both HTMX requests (tabs/search/pager) and custom fetch in globe.js
- Shows:
  - Loading overlay (skeleton)
  - Error overlay (retry)
*/

(function () {
  'use strict';

  const board = document.getElementById('board');
  const boardContent = document.getElementById('boardContent');
  const loadingEl = document.getElementById('boardLoading');
  const errorEl = document.getElementById('boardError');
  const retryBtn = document.getElementById('boardRetryBtn');

  if (!board || !boardContent) return;

  let lastUrl = '';

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
    }
  });

  function onHtmxError(e) {
    if (!isBoardRequest(e.detail)) return;
    const url = extractUrl(e.detail);
    showError(url);
  }

  document.body.addEventListener('htmx:responseError', onHtmxError);
  document.body.addEventListener('htmx:sendError', onHtmxError);
  document.body.addEventListener('htmx:timeout', onHtmxError);

})();
