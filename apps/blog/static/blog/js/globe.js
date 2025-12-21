/*
Globe integration (Three.js via globe.gl)

업데이트 목표:
- 정적 경로 하드코딩 제거(ManifestStaticFilesStorage/collectstatic 대응)
  -> window.TRAVEL_ATLAS_ASSETS(템플릿에서 {% static %}로 주입) 우선 사용
  -> 없으면 /static/... dev fallback
- GeoJSON(ISO 포함) 우선 로딩 -> 실패 시 topojson(110m) fallback
- 클릭 매핑: ISO A2/A3 우선, 없으면 name 매핑
- 보드 갱신은 fetch(+HX-Request)로 유지
- 204 No Content 응답이면 보드를 비우지 않음(보수적)
*/

(function () {
  'use strict';

  // =========================
  // 0) Static asset URLs
  // =========================
  // 템플릿(home.html)에서 아래처럼 주입해두면 배포(Manifest)에서도 안전함:
  // window.TRAVEL_ATLAS_ASSETS = {
  //   geojsonUrls: ["{% static 'blog/data/countries.simplified.geojson' %}", "{% static 'blog/data/countries.geojson' %}"],
  //   topojsonUrl: "{% static 'blog/vendor/world-atlas/countries-110m.json' %}",
  //   earthTextureUrl: "{% static 'blog/vendor/three-globe/earth-dark.jpg' %}",
  // };
  const ASSETS = window.TRAVEL_ATLAS_ASSETS || {};

  const GEOJSON_URLS = Array.isArray(ASSETS.geojsonUrls) && ASSETS.geojsonUrls.length
    ? ASSETS.geojsonUrls
    : [
        '/static/blog/data/countries.simplified.geojson',
        '/static/blog/data/countries.geojson',
      ];

  const WORLD_TOPOJSON_URL = ASSETS.topojsonUrl || '/static/blog/vendor/world-atlas/countries-110m.json';
  const EARTH_TEXTURE_URL = ASSETS.earthTextureUrl || '/static/blog/vendor/three-globe/earth-dark.jpg';

  // =========================
  // 1) Small helpers
  // =========================
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
    // 소문자 + 공백 정리 + 악센트 제거 + 흔한 구두점 제거
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
    // "대한민국(Korea)" / "대한민국 (Korea)" 같은 값에서 괄호 안 텍스트 추출
    const s = (displayName || '').toString();
    const m = s.match(/\(([^)]+)\)/);
    if (!m) return '';
    return (m[1] || '').trim();
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

  function polyIsoA2(poly) {
    const p = poly?.properties || {};
    const v =
      p.iso_a2 || p.ISO_A2 || p.iso2 || p.ISO2 ||
      p.A2 || p.a2 ||
      p['ISO3166-1-Alpha-2'] || p['iso3166-1-alpha-2'];
    return (v || '').toString().trim().toLowerCase();
  }

  function polyIsoA3(poly) {
    const p = poly?.properties || {};
    const v =
      p.iso_a3 || p.ISO_A3 || p.ADM0_A3 || p.adm0_a3 ||
      p.A3 || p.a3 ||
      p['ISO3166-1-Alpha-3'] || p['iso3166-1-alpha-3'];
    return (v || '').toString().trim().toLowerCase();
  }

  function polyName(poly) {
    const p = poly?.properties || {};
    // topojson(110m)은 대개 properties.name 사용
    // geojson은 name/NAME 등 케이스가 있으니 여러 키를 시도
    return (
      p.name || p.NAME || p.admin || p.ADMIN ||
      p.geounit || p.GEOUNIT ||
      ''
    ).toString();
  }

  async function fetchJson(url, cacheMode) {
    const res = await fetch(url, { cache: cacheMode || 'force-cache' });
    if (!res.ok) throw new Error(`fetch failed: ${url} (${res.status})`);
    return await res.json();
  }

  // =========================
  // 2) Board loading (fetch + HX-Request)
  // =========================
  let inflight = null;
  async function loadBoard(url) {
    const board = document.getElementById('board');
    if (!board) return;

    try {
      if (inflight) inflight.abort();
      inflight = new AbortController();

      const res = await fetch(url, {
        method: 'GET',
        headers: {
          'HX-Request': 'true',
          'X-Requested-With': 'XMLHttpRequest',
        },
        signal: inflight.signal,
        cache: 'no-store',
      });

      // ✅ 204면 보드를 비우지 않고 그대로 둠(보수적)
      if (res.status === 204) return;

      if (!res.ok) {
        // 실패 시 전체 이동(보수적)
        window.location.href = url;
        return;
      }

      const html = await res.text();
      board.innerHTML = html;

      // htmx attribute 다시 스캔
      if (window.htmx && typeof window.htmx.process === 'function') {
        window.htmx.process(board);
      }

      // history push
      window.history.pushState({}, '', url);

      // ✅ 기존 코드가 htmx:afterSwap을 기준으로 후처리하므로 이벤트를 board에 발생
      const evt = new CustomEvent('htmx:afterSwap', { bubbles: true });
      board.dispatchEvent(evt);

    } catch (e) {
      if (e && e.name === 'AbortError') return;
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

    const url = `/${encodeURIComponent(slug)}/`;
    loadBoard(url);
  }

  // =========================
  // 3) Main
  // =========================
  document.addEventListener('DOMContentLoaded', async () => {
    const mount = document.getElementById('globeMount');
    if (!mount) return;

    if (!hasWebGL()) return;

    // deps 체크
    if (typeof window.Globe !== 'function' || typeof window.topojson !== 'object') {
      return;
    }

    // Django -> JS
    const scriptTag = document.getElementById('globeCountriesData');
    const countries = scriptTag ? JSON.parse(scriptTag.textContent || '[]') : [];

    // slug 매핑 테이블
    const slugByIso2 = new Map();
    const slugByIso3 = new Map();
    const slugByName = new Map(); // fallback
    const iso2BySlug = new Map();
    const iso3BySlug = new Map();
    const nameEnBySlug = new Map();

    function addNameKey(name, slug) {
      const key = normName(name);
      if (!key) return;
      if (!slugByName.has(key)) slugByName.set(key, slug);
    }

    countries.forEach((c) => {
      if (!c || !c.slug) return;

      const iso2 = (c.iso_a2 || '').toString().trim().toLowerCase();
      const iso3 = (c.iso_a3 || '').toString().trim().toLowerCase();
      if (iso2 && !slugByIso2.has(iso2)) slugByIso2.set(iso2, c.slug);
      if (iso3 && !slugByIso3.has(iso3)) slugByIso3.set(iso3, c.slug);

      if (iso2) iso2BySlug.set(c.slug, iso2);
      if (iso3) iso3BySlug.set(c.slug, iso3);

      // name / name_en / 괄호 안 영문
      addNameKey(c.name, c.slug);
      addNameKey(c.name_en, c.slug);
      addNameKey(extractParenEn(c.name), c.slug);

      // aliases
      const aliases = c.aliases;
      if (typeof aliases === 'string' && aliases.trim()) {
        aliases
          .split(/[,;|]/)
          .map(s => s.trim())
          .filter(Boolean)
          .forEach((a) => addNameKey(a, c.slug));
      }

      // 선택 하이라이트용 대표 영문명(있으면)
      if (c.slug && (c.name_en || c.name)) {
        nameEnBySlug.set(c.slug, c.name_en || extractParenEn(c.name) || c.name || '');
      }
    });

    let selectedSlug =
      document.getElementById('globeArea')?.dataset.selectedCountrySlug ||
      getSelectedSlugFromPathname();

    function selectedIso2() {
      return (iso2BySlug.get(selectedSlug) || '').toString().trim().toLowerCase();
    }
    function selectedIso3() {
      return (iso3BySlug.get(selectedSlug) || '').toString().trim().toLowerCase();
    }

    // globe init
    const globe = window.Globe()(mount)
      .globeImageUrl(EARTH_TEXTURE_URL)
      .backgroundColor('#000')
      .showAtmosphere(true)
      .atmosphereColor('rgba(255,255,255,0.35)')
      .atmosphereAltitude(0.12);

    // size sync
    function syncSize() {
      const rect = mount.getBoundingClientRect();
      globe.width(Math.max(1, Math.floor(rect.width)));
      globe.height(Math.max(1, Math.floor(rect.height)));
    }
    syncSize();
    window.addEventListener('resize', syncSize, { passive: true });

    // controls
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

    // hover/selection styles
    let hoveredPoly = null;

    function isSelectedPoly(d) {
      // 1) ISO로 비교(가능하면 가장 안정적)
      const a2 = polyIsoA2(d);
      const a3 = polyIsoA3(d);
      if (a2 && selectedIso2() && a2 === selectedIso2()) return true;
      if (a3 && selectedIso3() && a3 === selectedIso3()) return true;

      // 2) fallback: 영문 name 비교
      const polyNm = normName(polyName(d));
      const selNameEn = normName(nameEnBySlug.get(selectedSlug) || '');
      const selParen = normName(extractParenEn(nameEnBySlug.get(selectedSlug) || ''));
      return (selNameEn && polyNm === selNameEn) || (selParen && polyNm === selParen);
    }

    const capColor = (d) => {
      if (isSelectedPoly(d)) return 'rgba(255,255,255,0.22)';
      if (hoveredPoly && d === hoveredPoly) return 'rgba(255,255,255,0.18)';
      return 'rgba(255,255,255,0.08)';
    };

    const altitude = (d) => {
      if (isSelectedPoly(d)) return 0.014;
      if (hoveredPoly && d === hoveredPoly) return 0.012;
      return 0.006;
    };

    globe
      .polygonsTransitionDuration(120)
      .polygonSideColor(() => 'rgba(0,0,0,0.0)')
      .polygonStrokeColor(() => 'rgba(255,255,255,0.18)')
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

        // ✅ ISO 우선 매핑
        const a2 = polyIsoA2(poly);
        const a3 = polyIsoA3(poly);
        let slug = '';

        if (a2 && slugByIso2.has(a2)) slug = slugByIso2.get(a2);
        else if (a3 && slugByIso3.has(a3)) slug = slugByIso3.get(a3);
        else {
          // fallback: name
          const name = polyName(poly);
          const key = normName(name);
          slug = slugByName.get(key) || '';
          if (!slug) {
            console.warn('[globe] no slug match for polygon:', { name, a2, a3 });
            return; // 보수적으로 아무것도 하지 않음
          }
        }

        selectedSlug = slug;
        setActiveCountryLink(selectedSlug);

        globe.polygonCapColor(globe.polygonCapColor());
        globe.polygonAltitude(globe.polygonAltitude());

        openBoardForSlug(slug);
      });

    // =========================
    // 4) Data load: GeoJSON -> topojson fallback
    // =========================
    async function loadPolygons() {
      // 4-1) GeoJSON 우선
      for (const url of GEOJSON_URLS) {
        try {
          const gj = await fetchJson(url, 'force-cache');
          const feats = gj?.features;
          if (Array.isArray(feats) && feats.length > 0) {
            globe.polygonsData(feats);
            console.log('[globe] polygons loaded from geojson:', url, feats.length);
            return;
          }
        } catch (e) {
          // 다음 후보로
        }
      }

      // 4-2) topojson fallback
      try {
        const world = await fetchJson(WORLD_TOPOJSON_URL, 'force-cache');
        const polys = window.topojson.feature(world, world.objects.countries).features;
        globe.polygonsData(polys);
        console.log('[globe] polygons loaded from topojson:', polys.length);
      } catch (e) {
        console.error('[globe] failed to load polygons:', e);
      }
    }

    await loadPolygons();

    // 초기 active 처리
    setActiveCountryLink(selectedSlug);

    // back/forward 시 동기화
    window.addEventListener('popstate', () => {
      const slug = getSelectedSlugFromPathname();
      if (!slug) return;
      selectedSlug = slug;
      setActiveCountryLink(selectedSlug);
      globe.polygonCapColor(globe.polygonCapColor());
      globe.polygonAltitude(globe.polygonAltitude());
    });

    // htmx로 board가 갱신되면 selectedSlug도 동기화
    document.body.addEventListener('htmx:afterSwap', (e) => {
      if (e.target && e.target.id === 'board') {
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
