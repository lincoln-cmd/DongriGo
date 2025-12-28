/*
Globe integration (globe.gl) - TopoJSON only

목표(보수적/안정 우선):
- TopoJSON(110m)만 사용
- 클릭 -> 보드 갱신: fetch(+HX-Request)
- 매핑 충돌 해결: name/name_en/괄호영문 > aliases > ISO 키 우선순위로 덮어쓰기
- 폴리곤 가시성 개선
*/

(function () {
  'use strict';

  const ASSETS = window.TRAVEL_ATLAS_ASSETS || {};
  const WORLD_TOPOJSON_URL = ASSETS.topojsonUrl || '/static/blog/vendor/world-atlas/countries-110m.json';
  const EARTH_TEXTURE_URL  = ASSETS.earthTextureUrl || '/static/blog/vendor/three-globe/earth-dark.jpg';

  const IS_DEV = (location.hostname === '127.0.0.1' || location.hostname === 'localhost');

  function bust(url) {
    if (!IS_DEV) return url;
    const sep = url.includes('?') ? '&' : '?';
    return `${url}${sep}v=${Date.now()}`;
  }

  function hasWebGL() {
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      return !!(window.WebGLRenderingContext && gl);
    } catch (_) {
      return false;
    }
  }

  function normName(value) {
    return (value || '')
      .toString()
      .toLowerCase()
      .trim()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[’'"().,]/g, '')
      .replace(/\s+/g, ' ');
  }

  function extractParenEn(displayName) {
    const s = (displayName || '').toString();
    const m = s.match(/\(([^)]+)\)/);
    return m ? (m[1] || '').trim() : '';
  }

  function getSelectedSlugFromPathname() {
    const parts = (window.location.pathname || '/').split('/').filter(Boolean);
    return parts.length >= 1 ? parts[0] : '';
  }

  function setActiveCountryLink(slug) {
    const links = document.querySelectorAll('#countryList .country-link');
    links.forEach((a) => {
      const href = a.getAttribute('href') || '';
      const m = href.match(/^\/([^/]+)\//);
      const linkSlug = m ? m[1] : '';
      if (slug && linkSlug === slug) a.classList.add('active');
      else a.classList.remove('active');
    });
  }

  function polyName(poly) {
    const p = poly?.properties || {};
    return (p.name || p.NAME || p.admin || p.ADMIN || '').toString();
  }

  async function fetchJson(url) {
    const reqUrl = IS_DEV ? bust(url) : url;
    const res = await fetch(reqUrl, { cache: IS_DEV ? 'no-store' : 'force-cache' });
    if (!res.ok) throw new Error(`fetch failed: ${url} (${res.status})`);
    return await res.json();
  }

  // ✅ 보드 갱신(fetch + HX-Request)
  // Phase2: 보드 "껍데기(#board)"는 고정, "내용(#boardContent)"만 갱신해야 함.
  let inflight = null;
  async function loadBoard(url) {
    const boardContent = document.getElementById('boardContent');
    if (!boardContent) {
      // 템플릿 구조가 다르면 안전하게 풀 페이지로 이동
      window.location.href = url;
      return;
    }

    const bs = window.DongriGoBoardState;
    if (bs && typeof bs.setLastUrl === 'function') bs.setLastUrl(url);
    if (bs && typeof bs.startLoading === 'function') bs.startLoading(url);

    try {
      if (inflight) inflight.abort();
      inflight = new AbortController();

      const res = await fetch(url, {
        method: 'GET',
        headers: { 'HX-Request': 'true', 'X-Requested-With': 'XMLHttpRequest' },
        signal: inflight.signal,
        cache: 'no-store',
      });

      if (!res.ok) {
        if (bs && typeof bs.stopLoading === 'function') bs.stopLoading();
        window.location.href = url;
        return;
      }

      const html = await res.text();
      boardContent.innerHTML = html;

      if (window.htmx && typeof window.htmx.process === 'function') {
        window.htmx.process(boardContent);
      }

      window.history.pushState({}, '', url);

      if (bs && typeof bs.stopLoading === 'function') bs.stopLoading();
      if (bs && typeof bs.hideError === 'function') bs.hideError();

      const evt = new CustomEvent('htmx:afterSwap', { bubbles: true });
      boardContent.dispatchEvent(evt);

    } catch (e) {
      if (e && e.name === 'AbortError') return;

      if (bs && typeof bs.showError === 'function') {
        bs.showError(url);
        return;
      }

      window.location.href = url;
    }
  }

  function openBoardForSlug(slug) {
    if (!slug) return;

    const wrap = document.querySelector('.wrap');
    if (wrap) {
      wrap.classList.remove('no-board');
      wrap.classList.add('has-board');
      wrap.dataset.hasBoard = '1';
    }

    const globeArea = document.getElementById('globeArea');
    if (globeArea) globeArea.dataset.selectedCountrySlug = slug;

    setActiveCountryLink(slug);
    loadBoard(`/${encodeURIComponent(slug)}/`);
  }

  // -------------------------
  // ✅ 우선순위 매핑(충돌 시 덮어쓰기)
  // -------------------------
  function isNumericishSlug(slug) {
    // "-99" 같은 케이스를 낮은 선호로 보기 위한 보조(동점일 때만 사용)
    return /^-?\d+$/.test((slug || '').toString().trim());
  }

  function betterSlug(newSlug, oldSlug) {
    // 동점(prio 같음)일 때만 사용: 숫자 슬러그보다 일반 슬러그 선호
    const n = isNumericishSlug(newSlug);
    const o = isNumericishSlug(oldSlug);
    if (n !== o) return o; // old가 numericish면 new가 더 낫다
    return false;
  }

  // map: key -> { slug, prio }
  const keyMap = new Map();

  function putKey(nameLike, slug, prio) {
    const key = normName(nameLike);
    if (!key) return;

    const prev = keyMap.get(key);
    if (!prev) {
      keyMap.set(key, { slug, prio });
      return;
    }

    if (prio > prev.prio) {
      keyMap.set(key, { slug, prio });
      return;
    }

    if (prio === prev.prio && betterSlug(slug, prev.slug)) {
      keyMap.set(key, { slug, prio });
      return;
    }
  }

  function getSlugForKey(nameLike) {
    const key = normName(nameLike);
    if (!key) return '';
    const v = keyMap.get(key);
    return v ? v.slug : '';
  }

  // 폴리곤에 __slug를 1회 캐싱
  function decoratePolys(polys) {
    for (const p of polys) {
      const nm = polyName(p);
      p.__slug = getSlugForKey(nm) || '';
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    const mount = document.getElementById('globeMount');
    if (!mount) return;
    if (!hasWebGL()) return;

    if (typeof window.Globe !== 'function' || typeof window.topojson !== 'object') {
      return;
    }

    // Django -> JS
    const scriptTag = document.getElementById('globeCountriesData');
    const countries = scriptTag ? JSON.parse(scriptTag.textContent || '[]') : [];

    // ✅ 우선순위로 keyMap 구성
    // prio: name_en(5) / name(4) / 괄호영문(4) / aliases(2) / iso(1)
    countries.forEach((c) => {
      if (!c || !c.slug) return;

      // 가장 강한 키들
      putKey(c.name_en, c.slug, 5);
      putKey(c.name, c.slug, 4);
      putKey(extractParenEn(c.name), c.slug, 4);

      // aliases(충돌 가능성이 높으니 낮게)
      const aliases = c.aliases;
      if (typeof aliases === 'string' && aliases.trim()) {
        aliases
          .split(/[,;|]/)
          .map(s => s.trim())
          .filter(Boolean)
          .forEach((a) => putKey(a, c.slug, 2));
      }

      // ISO는 참고용(TopoJSON 이름 매칭에 직접 쓰이진 않음)
      putKey(c.iso_a2, c.slug, 1);
      putKey(c.iso_a3, c.slug, 1);
    });

    let selectedSlug =
      document.getElementById('globeArea')?.dataset.selectedCountrySlug ||
      getSelectedSlugFromPathname();

    const globe = window.Globe()(mount)
      .globeImageUrl(EARTH_TEXTURE_URL)
      .backgroundColor('#000')
      .showAtmosphere(true)
      .atmosphereColor('#ffffff')
      .atmosphereAltitude(0.12);

    // 렌더 해상도 제한
    try {
      if (typeof globe.renderer === 'function') {
        const r = globe.renderer();
        if (r && typeof r.setPixelRatio === 'function') {
          r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
        }
      }
    } catch (_) {}

    function syncSize() {
      const rect = mount.getBoundingClientRect();
      globe.width(Math.max(1, Math.floor(rect.width)));
      globe.height(Math.max(1, Math.floor(rect.height)));
    }
    syncSize();
    window.addEventListener('resize', syncSize, { passive: true });

    const controls = globe.controls();
    if (controls) {
      controls.enablePan = false;
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
      controls.rotateSpeed = 0.35;
      controls.zoomSpeed = 0.7;
      controls.minDistance = 160;
      controls.maxDistance = 520;
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.6;
    }

    let hoveredPoly = null;

    function isSelectedPoly(d) {
      return !!(selectedSlug && d && d.__slug === selectedSlug);
    }

    const capColor = (d) => {
      if (isSelectedPoly(d)) return 'rgba(255,255,255,0.18)';
      if (hoveredPoly && d === hoveredPoly) return 'rgba(255,255,255,0.14)';
      return 'rgba(255,255,255,0.06)';
    };

    const altitude = (d) => {
      if (isSelectedPoly(d)) return 0.015;
      if (hoveredPoly && d === hoveredPoly) return 0.012;
      return 0.007;
    };

    globe
      .polygonsTransitionDuration(0)
      .polygonSideColor(() => 'rgba(0,0,0,0.0)')
      .polygonStrokeColor(() => 'rgba(255,255,255,0.35)')
      .polygonCapColor(capColor)
      .polygonAltitude(altitude)
      .polygonLabel((d) => polyName(d) || '')
      .onPolygonHover((poly) => {
        if (poly === hoveredPoly) return;
        hoveredPoly = poly;
        globe.polygonCapColor(globe.polygonCapColor());
        globe.polygonAltitude(globe.polygonAltitude());
      })
      .onPolygonClick((poly) => {
        if (!poly) return;

        const name = polyName(poly);
        const slug = getSlugForKey(name);

        if (IS_DEV) {
          console.log('[globe click]', { polyName: name, norm: normName(name), slug });
        }

        if (!slug) {
          console.warn('[globe] no slug match for polygon:', { name });
          return;
        }

        selectedSlug = slug;
        setActiveCountryLink(selectedSlug);

        globe.polygonCapColor(globe.polygonCapColor());
        globe.polygonAltitude(globe.polygonAltitude());

        openBoardForSlug(slug);
      });

    // ✅ TopoJSON only
    try {
      const world = await fetchJson(WORLD_TOPOJSON_URL);
      const polys = window.topojson.feature(world, world.objects.countries).features;

      decoratePolys(polys);
      globe.polygonsData(polys);

      console.log('[globe] polygons loaded from topojson:', polys.length);
    } catch (e) {
      console.error('[globe] failed to load topojson:', e);
    }

    setActiveCountryLink(selectedSlug);

    window.addEventListener('popstate', () => {
      const slug = getSelectedSlugFromPathname();
      if (!slug) return;
      selectedSlug = slug;
      setActiveCountryLink(selectedSlug);
      globe.polygonCapColor(globe.polygonCapColor());
      globe.polygonAltitude(globe.polygonAltitude());
    });

    // Phase2: swap target이 #boardContent로 바뀌었으므로 여기 타겟도 수정
    document.body.addEventListener('htmx:afterSwap', (e) => {
      if (e.target && e.target.id === 'boardContent') {
        const slug = getSelectedSlugFromPathname();
        if (!slug) return;
        selectedSlug = slug;
        setActiveCountryLink(selectedSlug);
        globe.polygonCapColor(globe.polygonCapColor());
        globe.polygonAltitude(globe.polygonAltitude());
      }
    });
  });
})();
