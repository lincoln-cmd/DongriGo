// lightbox.js
// - 이벤트 위임: HTMX로 #board 교체되어도 동작
// - 캡션: data-caption > figcaption > alt/title
// - 고해상도: data-full 우선
// - Prev/Next: 키보드 ←/→ + 버튼
// - 닫기: ESC + 배경/이미지 클릭(컨트롤 클릭은 예외)
// - ✅ 모바일 스와이프: 좌/우로 넘기기, 아래로 스와이프하면 닫기(선택)

(function () {
  "use strict";

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }
  function qsa(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  function init() {
    const lightbox = qs("#lightbox");
    const lightboxImg = qs("#lightboxImg");
    const lightboxCap = qs("#lightboxCap");

    if (!lightbox || !lightboxImg) return;

    // 컨트롤(없으면 JS가 생성)
    let prevBtn = qs(".lb-prev", lightbox);
    let nextBtn = qs(".lb-next", lightbox);

    if (!prevBtn || !nextBtn) {
      const prev = document.createElement("button");
      prev.type = "button";
      prev.className = "lb-control lb-prev";
      prev.setAttribute("aria-label", "Previous image");
      prev.textContent = "‹";

      const next = document.createElement("button");
      next.type = "button";
      next.className = "lb-control lb-next";
      next.setAttribute("aria-label", "Next image");
      next.textContent = "›";

      lightbox.appendChild(prev);
      lightbox.appendChild(next);

      prevBtn = prev;
      nextBtn = next;
    }

    let items = []; // { full, caption }
    let index = -1;

    function isOpen() {
      return lightbox.getAttribute("aria-hidden") === "false";
    }

    function pickCaption(img) {
      const dc = img.getAttribute("data-caption");
      if (dc && dc.trim()) return dc.trim();

      const fig = img.closest("figure");
      if (fig) {
        const fc = qs("figcaption", fig);
        if (fc && (fc.textContent || "").trim()) return (fc.textContent || "").trim();
      }
      return (img.getAttribute("alt") || img.getAttribute("title") || "").trim();
    }

    function pickFullSrc(img) {
      const df = img.getAttribute("data-full");
      if (df && df.trim()) return df.trim();
      return img.currentSrc || img.src;
    }

    function buildItemsFromBoard() {
      const board = qs("#board");
      if (!board) return [];

      const candidates = [
        ...qsa(".cover-img", board),
        ...qsa("#postContent img", board),
        ...qsa(".post-gallery img", board),
      ];

      const seen = new Set();
      const list = [];
      for (const img of candidates) {
        const full = pickFullSrc(img);
        if (!full) continue;
        if (seen.has(full)) continue;
        seen.add(full);
        list.push({ full, caption: pickCaption(img) });
      }
      return list;
    }

    function renderControls() {
      const many = items.length > 1;
      prevBtn.style.display = many ? "" : "none";
      nextBtn.style.display = many ? "" : "none";
    }

    function openLightboxAt(i) {
      if (!items.length) return;
      const safeIndex = ((i % items.length) + items.length) % items.length;
      index = safeIndex;
    
      const it = items[index];
    
      // ✅ 로딩 시작
      lightbox.classList.add("loading");
    
      // 로딩 이벤트 핸들러(한 번만)
      const onLoad = () => {
        lightbox.classList.remove("loading");
        lightboxImg.removeEventListener("load", onLoad);
        lightboxImg.removeEventListener("error", onError);
      };
      const onError = () => {
        lightbox.classList.remove("loading");
        lightboxImg.removeEventListener("load", onLoad);
        lightboxImg.removeEventListener("error", onError);
      };
    
      lightboxImg.addEventListener("load", onLoad);
      lightboxImg.addEventListener("error", onError);
    
      lightboxImg.src = it.full;
    
      if (lightboxCap) lightboxCap.textContent = it.caption || "";
    
      lightbox.setAttribute("aria-hidden", "false");
      lightbox.classList.add("open");
      document.documentElement.classList.add("lb-open");
    
      renderControls();
    }

    function closeLightbox() {
      lightbox.setAttribute("aria-hidden", "true");
      lightbox.classList.remove("open");
      lightbox.classList.remove("loading");
      document.documentElement.classList.remove("lb-open");

      lightboxImg.removeAttribute("src");
      if (lightboxCap) lightboxCap.textContent = "";

      items = [];
      index = -1;
    }

    function next() {
      if (!items.length) return;
      openLightboxAt(index + 1);
    }

    function prev() {
      if (!items.length) return;
      openLightboxAt(index - 1);
    }

    // ✅ board 내부 이미지 클릭 → 열기(이벤트 위임)
    document.addEventListener("click", (e) => {
      const img = e.target && e.target.closest ? e.target.closest("#board img") : null;
      if (!img) return;

      e.preventDefault();

      items = buildItemsFromBoard();
      const clickedFull = pickFullSrc(img);
      const found = items.findIndex((x) => x.full === clickedFull);
      openLightboxAt(found >= 0 ? found : 0);
    });

    // ✅ 닫기(배경/이미지 클릭): 단, 컨트롤 클릭은 닫지 않음
    lightbox.addEventListener("click", (e) => {
      if (e.target && e.target.closest && e.target.closest(".lb-control")) return;
      closeLightbox();
    });

    // 컨트롤 클릭(전파 막기)
    prevBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      prev();
    });
    nextBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      next();
    });

    // ✅ 키보드
    document.addEventListener("keydown", (e) => {
      if (!isOpen()) return;
      if (e.key === "Escape") closeLightbox();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "ArrowRight") next();
    });

    // =========================================================
    // ✅ Touch / Swipe (mobile)
    // - 좌/우 스와이프: prev/next
    // - 아래로 스와이프: close (옵션, 임계값 높게)
    // =========================================================
    let startX = 0, startY = 0, startT = 0;
    let tracking = false;

    function onTouchStart(e) {
      if (!isOpen()) return;
      if (!e.touches || e.touches.length !== 1) return;

      // 컨트롤 버튼 터치는 스와이프 추적 제외
      const target = e.target;
      if (target && target.closest && target.closest(".lb-control")) return;

      const t = e.touches[0];
      startX = t.clientX;
      startY = t.clientY;
      startT = Date.now();
      tracking = true;
    }

    function onTouchMove(e) {
      if (!tracking) return;
      // 페이지 스크롤/튐을 줄이기 위해 열려있을 때는 기본 스크롤 방지
      // (단, iOS에서 passive 기본이라 addEventListener 옵션을 false로 둬야 함)
      e.preventDefault();
    }

    function onTouchEnd(e) {
      if (!tracking) return;
      tracking = false;

      const changed = (e.changedTouches && e.changedTouches[0]) ? e.changedTouches[0] : null;
      if (!changed) return;

      const dx = changed.clientX - startX;
      const dy = changed.clientY - startY;
      const dt = Date.now() - startT;

      const absX = Math.abs(dx);
      const absY = Math.abs(dy);

      // 너무 느린 드래그는 무시
      if (dt > 900) return;

      // 임계값
      const SWIPE_X = 60;
      const SWIPE_Y = 90;

      // 좌/우 우선
      if (absX > absY && absX >= SWIPE_X) {
        if (dx < 0) next();
        else prev();
        return;
      }

      // 아래로 스와이프 닫기(원하지 않으면 이 블록 삭제)
      if (absY > absX && dy >= SWIPE_Y) {
        closeLightbox();
      }
    }

    // ✅ passive:false 필요(특히 iOS) - move에서 preventDefault 쓰기 위함
    lightbox.addEventListener("touchstart", onTouchStart, { passive: true });
    lightbox.addEventListener("touchmove", onTouchMove, { passive: false });
    lightbox.addEventListener("touchend", onTouchEnd, { passive: true });

    if (!lightbox.hasAttribute("aria-hidden")) {
      lightbox.setAttribute("aria-hidden", "true");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
