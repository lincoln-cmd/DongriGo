/*
Globe integration (Three.js via globe.gl)

보수적으로 안정화:
- topojson(110m)만 사용 (무거운 geojson 로드 시도 제거)
- 클릭 시 보드 갱신은 fetch(+HX-Request)로 강제 (hidden link click 의존 제거)
- Country.name이 "한글(영문)"이어도 매핑되도록:
  - name_en / aliases / 괄호 안 영문 추출을 모두 키로 등록
*/

(function () {
  'use strict';

  // ✅ 로컬 정적 파일(네가 브라우저에서 정상 출력 확인한 경로)
  const WORLD_TOPOJSON_URL = '/static/blog/vendor/world-atlas/countries-110m.json';
  const EARTH_TEXTURE_URL = '/static/blog/vendor/three-globe/earth-dark.jpg';

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
    const inner = (m[1] || '').trim();
    // 괄호 안이 완전 한글이어도 일단 반환은 하되,
    // 실제 topojson name(영문) 매핑은 name_en/aliases가 주력이라 큰 문제 없음
    return inner;
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

  // ✅ 보드 갱신을 fetch로 강제 + HX-Request 헤더로 partial(_board.html) 받기
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

      // ✅ 기존 코드가 htmx:afterSwap을 기준으로 후처리(읽기모드/선택동기화)하므로 이벤트를 “board 타겟”으로 발생
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

    const slugByName = new Map();
    const nameBySlug = new Map();

    function addNameKey(name, slug) {
      const key = normName(name);
      if (!key) return;
      if (!slugByName.has(key)) slugByName.set(key, slug);
    }

    countries.forEach((c) => {
      if (!c || !c.slug) return;

      // name / name_en / 괄호 안 영문
      addNameKey(c.name, c.slug);
      addNameKey(c.name_en, c.slug);
      addNameKey(extractParenEn(c.name), c.slug);

      // iso
      addNameKey(c.iso_a2, c.slug);
      addNameKey(c.iso_a3, c.slug);

      // aliases (문자열)
      const aliases = c.aliases;
      if (typeof aliases === 'string' && aliases.trim()) {
        aliases.split(/[,;|]/).map(s => s.trim()).filter(Boolean).forEach((a) => addNameKey(a, c.slug));
      }

      // reverse
      if (c.slug && (c.name || c.name_en)) {
        nameBySlug.set(c.slug, c.name_en || c.name || '');
      }
    });

    let selectedSlug =
      document.getElementById('globeArea')?.dataset.selectedCountrySlug ||
      getSelectedSlugFromPathname();

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
      // selectedSlug 기반으로 “대표 영문명”을 비교 (폴리곤은 영문 name)
      const polyName = normName(d?.properties?.name);
      const selectedName = normName(nameBySlug.get(selectedSlug) || '');
      // selectedName이 한글(영문)이면 괄호 안 영문도 비교
      const selectedParen = normName(extractParenEn(nameBySlug.get(selectedSlug) || ''));
      return (selectedName && polyName === selectedName) || (selectedParen && polyName === selectedParen);
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
      .polygonLabel((d) => d?.properties?.name || '')
      .onPolygonHover((poly) => {
        if (poly === hoveredPoly) return;
        hoveredPoly = poly;
        globe.polygonCapColor(globe.polygonCapColor());
        globe.polygonAltitude(globe.polygonAltitude());
      })
      .onPolygonClick((poly) => {
        if (!poly) return;
        const name = poly?.properties?.name;
        const key = normName(name);
        const slug = slugByName.get(key);

        if (!slug) {
          // 네가 찍어준 로그 형태 유지
          console.warn('[globe] no slug match for polygon name:', name);
          return;
        }

        selectedSlug = slug;
        setActiveCountryLink(selectedSlug);

        globe.polygonCapColor(globe.polygonCapColor());
        globe.polygonAltitude(globe.polygonAltitude());

        openBoardForSlug(slug);
      });

    // topojson load (가볍고 빠름)
    try {
      const world = await fetch(WORLD_TOPOJSON_URL, { cache: 'force-cache' }).then((r) => r.json());
      const polys = window.topojson.feature(world, world.objects.countries).features;
      globe.polygonsData(polys);
      console.log('[globe] polygons loaded:', polys.length);
    } catch (e) {
      return;
    }

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

    // htmx로 board가 갱신되면 selectedSlug도 동기화 (기존 로직 유지)
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
