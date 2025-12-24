# DongriGo

DongriGo는 국가별 **역사·문화·여행 정보(가이드)**와 **개인 여행 기록(로그)**를 함께 제공하는 콘텐츠 사이트입니다.  
글 작성/편집은 **관리자(Django admin)만 가능**하며, 방문자는 **읽기 전용**으로 콘텐츠를 탐색합니다.  
이미지/첨부 파일은 **Cloudinary**에 저장합니다. *(민감한 키/토큰은 레포에 포함하지 않습니다.)*

- 서비스: https://dongrigo.onrender.com  
- Admin: https://dongrigo.onrender.com/admin
- Notion: https://www.notion.so/Django-DongriGo-2d2c2fb07df980c6b238c7c53d54ae59

---

## Core Features

- **관리자 전용 콘텐츠 관리**
  - Django admin에서 글 작성/수정/삭제

- **콘텐츠 2트랙**
  - **Guide**: 국가별 역사/문화/여행 정보(지식형)
  - **Log**: 개인 여행 기록(일기/후기형)

- **탐색**
  - 3D Globe에서 국가 클릭 → 보드(게시물 목록/상세) 로드
  - 카테고리 탭: `Travel / History / Culture / My Log`
  - 검색: 제목/본문 기반

- **이미지**
  - Cloudinary 연동 업로드
  - 본문 이미지 토큰(`[[img:ID]]`) 삽입 렌더
  - 본문에 사용되지 않은 이미지만 하단 갤러리로 자동 출력
  - Lightbox(확대/닫기/이전/다음)

- **Admin UX 개선**
  - 이미지 토큰 자동 삽입 버튼
  - 라이브 프리뷰(서버 렌더와 동일한 결과)
  - 마크다운 툴바(빠른 서식 입력)

---

## Content Structure

- **Country (국가)**
- **Post**
  - `category`: `Travel` | `History` | `Culture` | `My Log`
  - `country` 연결
  - `slug` (게시물 URL 식별자)
  - `cover_image` / `images` (갤러리/본문 삽입)
- **PostImage**
  - 게시물별 이미지 다중 업로드
  - 표시 순서(`order`) 지원

---

## Tech Stack

### App
- **Backend**: Python 3.12, Django 6
- **Frontend**: Django Templates + HTMX
- **3D Globe**: globe.gl (Three.js 기반), TopoJSON/GeoJSON 데이터
- **Static files**: WhiteNoise
- **Media (Images)**: Cloudinary + django-cloudinary-storage
- **Database (prod)**: PostgreSQL
- **Local dev**: SQLite (옵션)

### Deployment
- **Hosting**: Render Web Service
- **DB**: Render Postgres
- **WSGI**: gunicorn
- **CI/CD**: GitHub → Render 자동 배포

---

## Local Development

### 1) Setup

> 아래 명령은 예시입니다. (가상환경 생성/활성화 후 진행)

    pip install -r requirements.txt

### 2) Environment (.env)

프로젝트 루트에 `.env` 파일을 만들고 아래 형태로 세팅합니다.  
**절대 레포에 커밋하지 않습니다.**

    DEBUG=1
    SECRET_KEY=change-me

    ALLOWED_HOSTS=127.0.0.1,localhost

    # Cloudinary
    USE_CLOUDINARY=1
    CLOUDINARY_URL=cloudinary://<API_KEY>:<API_SECRET>@<CLOUD_NAME>
    CLOUDINARY_CLOUD_NAME=<CLOUD_NAME>
    CLOUDINARY_API_KEY=<API_KEY>
    CLOUDINARY_API_SECRET=<API_SECRET>

### 3) Run (dev)

    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver

---

## Production Deploy (Render)

### Repo files used by Render
- `requirements.txt`
- `.python-version`
- `build.sh`

참고: `build.sh`는 Render build 단계에서 실행되며, 일반적으로 아래를 수행합니다.
- `pip install -r requirements.txt`
- `python manage.py collectstatic --noinput`

### Render Web Service Settings (권장)

**Build Command**

    ./build.sh

**Start Command**

    gunicorn config.wsgi:application --bind 0.0.0.0:$PORT

### Environment variables (Render)

Render Web Service → Environment에서 다음을 설정합니다.  
(민감정보는 Secret으로 등록 권장)

    DEBUG=0
    SECRET_KEY=<prod-secret>

    ALLOWED_HOSTS=<your-service>.onrender.com

    USE_CLOUDINARY=1
    CLOUDINARY_URL=cloudinary://<API_KEY>:<API_SECRET>@<CLOUD_NAME>

    DATABASE_URL=<Render Postgres URL>

### Initial Setup on Render (Shell)

배포가 올라온 뒤 Render Shell에서 아래 순서대로 실행합니다.

#### 1) Migrate

    python manage.py migrate

#### 2) Create superuser

    python manage.py createsuperuser

이미 생성된 superuser가 있다면 다시 만들 필요는 없습니다.  
다만 새 계정을 추가로 만들고 싶으면 다른 username으로 생성하면 됩니다.

#### 3) Seed data (권장)

    python manage.py seed_prod --force

---

## Data / Fixtures

배포 초기 데이터는 `fixtures/prod_seed.json`를 사용합니다.

운영(Postgres)에서 초기 데이터를 넣을 때는 fixture loaddata 또는 seed command를 사용합니다.

### Load fixture manually

    python manage.py loaddata fixtures/prod_seed.json

### Seed command (권장)

    python manage.py seed_prod --force

### Rebuild fixture (local에서 생성)

Windows 환경에서 인코딩 문제를 피하려면 UTF-8로 dump합니다.

    $env:PYTHONUTF8="1"
    python -X utf8 manage.py dumpdata blog.Country blog.Post blog.PostImage --indent 2 --output fixtures/prod_seed.json

---

## Notes / Troubleshooting

### 1) Render에서 `ModuleNotFoundError: No module named 'app'`

Start Command가 `gunicorn app:app`처럼 잘못 잡힌 케이스입니다.  
✅ 아래로 수정:

    gunicorn config.wsgi:application --bind 0.0.0.0:$PORT

### 2) `DisallowedHost: Invalid HTTP_HOST header`

`ALLOWED_HOSTS`에 서비스 도메인이 빠진 케이스입니다.  
✅ Render 환경변수에 추가:

    ALLOWED_HOSTS=<your-service>.onrender.com

### 3) `requirements.txt`에 `@ file:///...` 경로가 섞여서 빌드 실패

Conda/로컬 build artifact 경로가 포함된 freeze 결과일 수 있습니다.  
✅ 해결: `requirements.txt`에서 `@ file:///...` 줄 제거 후 정상적인 버전 핀으로 교체

예: `asgiref==3.11.0` 처럼

### 4) Fixture 로드 시 `UnicodeDecodeError` (utf-8 decode 실패)

fixture 파일이 UTF-8이 아닌 인코딩으로 생성된 케이스입니다.  
✅ 해결: UTF-8로 재생성 후 커밋/배포

### 5) Fixture 로드 시 `value too long for type character varying(2)`

예: `iso_a2` 필드가 2글자 제한인데 `CN-TW`, `-99` 같은 값이 들어간 케이스입니다.  
✅ 해결(둘 중 하나 선택):

- (권장) 시딩/fixture에서 해당 값을 2글자 규칙에 맞게 정규화
- 또는 모델 필드 길이를 늘리고 마이그레이션(규칙 변경이므로 신중)

### 6) 데이터가 비어 보이는 현상 (Globe/검색/국가 목록이 없음)

운영 DB(Postgres)에 seed/fixture가 들어가지 않은 상태일 가능성이 큽니다.  
✅ 해결:

    python manage.py migrate
    python manage.py seed_prod --force

---

## Post Exclusion Part (자세한 사항은 `.gitignore` 참조)

- `.env` / `SECRET_KEY` 등 민감정보가 포함된 파일
- 대용량 파일 (GeoJSON 등의 100MB 초과 파일은 `.gitignore`로 제외될 수 있음)
- `collectstatic` 결과물(`staticfiles/`): 배포 환경에서 생성하므로 제외
- OS/editor extras: `.swp`, `.swo`, `.vscode/*` 등

---

## Roadmap (고도화 예정)

(**기반 안정화 → UX 개선 → 기능 확장 → 자동화/운영** 순으로 정리)

### ✅ Phase 0 — Baseline (완료)
-  [x]Django admin 기반 콘텐츠 작성/편집
- [x] 3D Globe 국가 클릭 → HTMX 보드 로드
- [x]검색/탭 기반 탐색
- [x]이미지 토큰(`[[img:ID]]`) 삽입 렌더 + 하단 갤러리 분리
- [x]Lightbox(확대/닫기/이동)
- [x]Admin UX(토큰 삽입 버튼, 라이브 프리뷰, 마크다운 툴바)
- [x]Render + Postgres + Cloudinary 운영

### 🧱 Phase 1 — 콘텐츠/데이터 안정화 (권장 우선순위 높음)
- [ ]Country/slug/iso 정합성 검사 & 자동 정규화(시딩/관리용 커맨드 포함)
- [ ]국가 데이터 “재시딩 안전성” 강화(중복 방지, `--force` 동작 명확화)
- [ ]게시물 slug 정책 고도화(중복 처리, 한글→slug 규칙 고정, 변경 시 리다이렉트 옵션)
- [ ]Admin에서 Country/Posts 데이터 검증(iso 길이, slug 중복, alias 형식) 경고 표시
- [ ]에러/로그 기반 운영 점검(DisallowedHost, static/media, seed/migrate)

### 🎛️ Phase 2 — UX 개선 (방문자/관리자 체감)
- [ ]국가 클릭 시 로딩/실패 상태 UI(스켈레톤, “해당 국가 콘텐츠 없음” 안내)
- [ ]검색 UX 강화(자동완성/최근 검색, 결과 하이라이트, 빈 결과 메시지)
- [ ]게시물 목록 정렬 옵션(최신/인기/카테고리/태그)
- [ ]라이트박스 UX 개선(키보드 방향키 이동, 이미지 카운터, 썸네일 스트립)
- [ ]반응형/모바일 최적화(보드 레이아웃, 터치 UX)

### 🧩 Phase 3 — 기능 확장 (콘텐츠 모델 확장)
- [ ]City/Region 모델 추가 + Country 연계(도시/지역별 글 분류)
- [ ]태그 시스템(태그 페이지, 태그 검색/필터)
- [ ]시리즈/목차(장문 가이드 구성용) + TOC 자동 생성
- [ ]즐겨찾기/북마크(로그인 없이 로컬 저장 또는 로그인 기반)
- [ ]관련 글 추천(같은 국가/태그/카테고리 기반)
- [ ]다국어 지원(i18n): 사용자 언어 선택
- [ ]AI/API 기반 자동 번역(서버/클라이언트 렌더링 방식 선택)
- [ ]번역 캐시/버전 관리(원문 수정 시 번역 무효화 정책)

### 🔐 Phase 4 — 계정/권한/커뮤니티
- [ ]댓글(스팸 방지/모더레이션 포함)
- [ ]구독/알림(국가/태그 구독, 이메일 알림은 선택)
- [ ]간단한 사용자 인증(로그인/소셜 로그인)

### 🧰 Phase 5 — 운영/성능/SEO (장기 운영 필수)
- [ ]SEO 확장: `sitemap.xml`, `robots.txt`, OpenGraph/Meta 고도화
- [ ]성능: 캐싱(페이지/쿼리), 이미지 최적화(lqip/resize), CDN 옵션 검토
- [ ]관측성: 에러 트래킹(Sentry 등), 성능 모니터링
- [ ]백업/복구 플로우 문서화(DB 백업, 미디어 보존, 시딩/마이그레이션 절차)
- [ ]보안: CSP/보안 헤더, 관리자 접근 제한(필요 시 IP 제한/2FA)
- [ ]AI 기반 멀티미디어 생성 파이프라인(이미지→애니메이션, 글→TTS)
- [ ]비동기 작업 큐(예: Celery/RQ) + 작업 상태/재시도 정책
- [ ]생성 결과 캐싱/버저닝(원문/이미지 변경 시 재생성)
- [ ]비용/레이트리밋/저작권 정책 + 관측성(Sentry/메트릭)

### Roadmap 운영 규칙
- **Phase 1(데이터 안정화)**를 먼저 끝내면 배포/운영에서 데이터 깨짐·시딩 실패·slug 불일치 같은 사고를 크게 줄일 수 있다.
- 이후 **Phase 2(UX 개선)**로 사용자 체감 품질을 올리고, **Phase 3(기능 확장)**에서 모델을 넓혀가면 유지보수가 수월하다.
- 댓글/계정 기능은 운영 부담이 커질 수 있으니(스팸/모더레이션/보안) 필요성이 확실할 때 **Phase 4**로 진행한다.
