// lightbox.js
// - 이벤트 위임: HTMX로 #board 교체되어도 동작
// - 캡션: data-caption > figcaption > alt/title
// - 고해상도: data-full 우선
// - Prev/Next: 키보드 ←/→ + 버튼
// - ✅ 카운터: "현재/전체" 표시
// - ✅ 썸네일 스트립: 하단 썸네일 클릭으로 이동
// - 닫기: ESC + 배경/이미지 클릭(컨트롤/썸네일 클릭은 예외)
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

    // 컨테이너(이미지/캡션이 들어있는 첫 번째 child div)
    const inner = lightbox.querySelector("div") || lightbox;

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

    // ✅ Counter (없으면 생성)
    let counterEl = qs(".lb-counter", lightbox);
    if (!counterEl) {
      const c = document.createElement("div");
      c.className = "lb-counter";
      c.setAttribute("aria-hidden", "true");
      c.textContent = "";
      lightbox.appendChild(c);
      counterEl = c;
    }

    // ✅ Thumbnails strip (없으면 생성)
    let thumbsEl = qs(".lb-thumbs", lightbox);
    if (!thumbsEl) {
      const t = document.createElement("div");
      t.className = "lb-thumbs";
      t.setAttribute("aria-hidden", "true");
      t.innerHTML = `<div class="lb-thumbs__track" role="list"></div>`;
      lightbox.appendChild(t);
      thumbsEl = t;
    }
    const thumbsTrack = qs(".lb-thumbs__track", thumbsEl);

    let items = []; // { full, thumb, caption }
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

    function pickThumbSrc(img) {
      // 썸네일은 현재 렌더링된 src가 가장 안전
      return img.currentSrc || img.src;
    }

    function buildItemsFromBoard() {
      const board = qs("#board");
      if (!board) return [];

      const candidates = [
        ...qsa(".cover-img", board),
        ...qsa("#postContent img", board),
        ...qsa(".post-gallery img", board),
        ...qsa(".gallery img", board),
      ];

      const seen = new Set();
      const list = [];
      for (const img of candidates) {
        const full = pickFullSrc(img);
        if (!full) continue;
        if (seen.has(full)) continue;

        seen.add(full);
        list.push({
          full,
          thumb: pickThumbSrc(img) || full,
          caption: pickCaption(img),
        });
      }
      return list;
    }

    function renderControls() {
      const many = items.length > 1;
      prevBtn.style.display = many ? "" : "none";
      nextBtn.style.display = many ? "" : "none";
    }

    function renderCounter() {
      if (!counterEl) return;
      if (!items.length || index < 0) {
        counterEl.textContent = "";
        counterEl.style.display = "none";
        return;
      }
      counterEl.textContent = `${index + 1} / ${items.length}`;
      counterEl.style.display = "";
    }

    function clearThumbs() {
      if (!thumbsTrack) return;
      thumbsTrack.innerHTML = "";
    }

    function buildThumbs() {
      if (!thumbsTrack) return;
      clearThumbs();

      if (items.length <= 1) {
        thumbsEl.style.display = "none";
        return;
      }

      thumbsEl.style.display = "";

      items.forEach((it, i) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "lb-thumb";
        btn.setAttribute("role", "listitem");
        btn.setAttribute("aria-label", `Open image ${i + 1}`);
        btn.dataset.index = String(i);

        const img = document.createElement("img");
        img.alt = "";
        img.loading = "lazy";
        img.src = it.thumb || it.full;

        btn.appendChild(img);

        btn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation(); // 배경 클릭 닫기 방지
          openLightboxAt(i, { keepThumbs: true });
        });

        thumbsTrack.appendChild(btn);
      });
    }

    function setActiveThumb() {
      if (!thumbsTrack) return;
      const nodes = qsa(".lb-thumb", thumbsTrack);
      nodes.forEach((n) => n.classList.remove("is-active"));
      const active = thumbsTrack.querySelector(`.lb-thumb[data-index="${index}"]`);
      if (active) {
        active.classList.add("is-active");
        // 활성 썸네일이 화면 밖이면 살짝 스크롤
        if (active.scrollIntoView) {
          active.scrollIntoView({ block: "nearest", inline: "nearest" });
        }
      }
    }

    function openLightboxAt(i, opts) {
      opts = opts || {};
      if (!items.length) return;

      const safeIndex = ((i % items.length) + items.length) % items.length;
      index = safeIndex;

      const it = items[index];

      // ✅ 로딩 시작
      lightbox.classList.add("loading");

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
      renderCounter();

      // ✅ 처음 오픈할 때만 썸네일 구성(또는 items 갱신 시)
      if (!opts.keepThumbs) buildThumbs();
      setActiveThumb();
    }

    function closeLightbox() {
      lightbox.setAttribute("aria-hidden", "true");
      lightbox.classList.remove("open");
      lightbox.classList.remove("loading");
      document.documentElement.classList.remove("lb-open");

      lightboxImg.removeAttribute("src");
      if (lightboxCap) lightboxCap.textContent = "";

      if (counterEl) {
        counterEl.textContent = "";
        counterEl.style.display = "none";
      }
      if (thumbsEl) {
        thumbsEl.style.display = "none";
        clearThumbs();
      }

      items = [];
      index = -1;
    }

    function next() {
      if (!items.length) return;
      openLightboxAt(index + 1, { keepThumbs: true });
    }

    function prev() {
      if (!items.length) return;
      openLightboxAt(index - 1, { keepThumbs: true });
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

    // ✅ 닫기(배경/이미지 클릭): 단, 컨트롤/썸네일 클릭은 닫지 않음
    lightbox.addEventListener("click", (e) => {
      if (e.target && e.target.closest && e.target.closest(".lb-control")) return;
      if (e.target && e.target.closest && e.target.closest(".lb-thumb")) return;
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

      const target = e.target;
      if (target && target.closest && target.closest(".lb-control")) return;
      if (target && target.closest && target.closest(".lb-thumb")) return;

      const t = e.touches[0];
      startX = t.clientX;
      startY = t.clientY;
      startT = Date.now();
      tracking = true;
    }

    function onTouchMove(e) {
      if (!tracking) return;
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

      if (dt > 900) return;

      const SWIPE_X = 60;
      const SWIPE_Y = 90;

      if (absX > absY && absX >= SWIPE_X) {
        if (dx < 0) next();
        else prev();
        return;
      }

      if (absY > absX && dy >= SWIPE_Y) {
        closeLightbox();
      }
    }

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
