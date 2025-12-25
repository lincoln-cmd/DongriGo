cat > docs/phase0/ARCHITECTURE.md << 'EOF'
# DongriGo Architecture (Phase 0 Baseline)

버전: v1.0  
기준일: 2025-12-25  
대상: 운영(Render + PostgreSQL + Cloudinary) 및 로컬 개발 환경

---

## 1. 목적과 범위

DongriGo는 국가별 **역사·문화·여행 가이드(Guide)**와 **개인 여행 기록(Log)**을 함께 제공하는 콘텐츠 사이트다.  
콘텐츠 작성/편집은 **관리자(Django Admin)만 가능**하며, 방문자는 **읽기 전용**으로 콘텐츠를 탐색한다.

이 문서는 “현재 운영 가능한 베이스라인(Phase 0~1)” 기준의 시스템 아키텍처와 주요 흐름을 정리한다.

---

## 2. 기술 스택 요약

- Backend: Python 3.12, Django 6
- Frontend: Django Templates + HTMX
- 3D Globe: globe.gl (Three.js 기반)
- Static: WhiteNoise (+ Render에서 collectstatic)
- Media: Cloudinary (+ django-cloudinary-storage)
- DB: 운영(Render PostgreSQL), 로컬(SQLite)
- Deploy: GitHub push → Render 자동 빌드/배포, Gunicorn 실행

---

## 3. 시스템 구성도 (Logical)

```mermaid
flowchart LR
  U[Visitor Browser] -->|HTTP| W[Render Web Service\nGunicorn + Django + WhiteNoise]
  A[Admin User] -->|/admin| W

  W -->|SQL| DB[(Render PostgreSQL)]
  W -->|Upload/Fetch| C[Cloudinary Media Storage]

  U -->|HTMX request\n(country/category/search)| W
  U -->|globe.gl click\nselect country| U
```

설명:
- 브라우저에서 globe.gl로 국가를 선택하면, 페이지 내 보드 영역이 HTMX로 서버에 요청을 보내고 서버가 HTML partial을 반환한다.
- 텍스트/메타데이터는 DB(PostgreSQL/SQLite)에 저장되고, 이미지 파일은 Cloudinary에 저장된다.

---

## 4. 데이터 모델 (요약)

### 4.1 Country
- 식별: `slug`
- ISO: `iso_a2(2)`, `iso_a3(3)` (정규화/검증 대상)
- 표시명: `name`, `name_ko`, `name_en`
- aliases: 대체 명칭 문자열(정규화/검증 대상)
- flag_image: Cloudinary 저장 가능

### 4.2 Post
- FK: `country`
- category: Travel / History / Culture / My Log
- slug: 게시물 URL 식별자(중복 방지 및 변경 시 링크 보존)
- content: Markdown + `[[img:ID]]` 토큰 방식
- cover_image: 대표 이미지(Cloudinary)
- 발행: `is_published`, `published_at`

### 4.3 PostImage
- FK: `post`
- image: Cloudinary 이미지 파일
- order: 표시 순서(10 단위 자동 정렬 정책)

### 4.4 SeedMeta (운영 안정화)
- fixture 해시를 기록해 `seed_prod`를 “멱등”하게 만든다.
- 동일 fixture면 재실행 시 스킵(hash match).

### 4.5 PostSlugHistory (링크 보존)
- Post의 slug/country/category 변경 시 “이전 URL 키”를 저장한다.
- 예전 URL로 접근하면 최신 URL로 301 redirect.

---

## 5. 핵심 사용자 흐름

### 5.1 방문자(읽기 전용)
1) 홈 진입 → 3D Globe 표시  
2) 국가 선택 → HTMX로 보드 영역 갱신(목록/검색/탭)  
3) 게시물 상세 진입 → Markdown 렌더 + 이미지 토큰 치환  
4) 이미지 클릭 → Lightbox로 확대/이동

### 5.2 관리자(Admin)
1) /admin 접속  
2) Country/Post/PostImage 관리(작성/수정/삭제)  
3) 이미지 업로드 후 토큰(`[[img:ID]]`)을 본문에 삽입  
4) 라이브 프리뷰로 서버 렌더 결과 확인

---

## 6. 콘텐츠 렌더링 규칙

### 6.1 Markdown
- Post.content는 Markdown으로 작성된다.
- 서버에서 Markdown → HTML로 변환 후, 허용 태그/속성 기반 sanitize 처리(안전 목적).

### 6.2 이미지 토큰 `[[img:ID]]`
- PostImage의 id를 사용하여 본문에 이미지를 삽입한다.
- 본문에서 사용되지 않은 이미지는 하단 갤러리로 자동 출력된다.
- (보수적 정책) 해당 Post에 연결된 이미지만 본문 토큰으로 치환한다.

---

## 7. 배포/운영 흐름

### 7.1 Render 배포
- GitHub push → Render 자동 build
- Build: `./build.sh` (requirements 설치 + collectstatic)
- Start: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`

### 7.2 운영 초기화(필수 커맨드)
Render Shell 기준:

- 마이그레이션
  - `python manage.py migrate`
- 시드(초기 데이터)
  - `python manage.py seed_prod`  (상황에 따라 `--force` 1회 사용 가능)
- 정합성 점검/보수
  - `python manage.py check_integrity --fix --json`
- 운영 자가진단
  - `python manage.py ops_check --json`

---

## 8. 운영 리스크와 방어 장치(Phase 1 결과 요약)

- 재시딩 사고 방지: SeedMeta(해시 기반 스킵)
- slug 변경 링크 깨짐 방지: PostSlugHistory + 301 redirect
- Admin 입력 실수 방지: ISO/aliases 정규화 및 경고 표시
- 운영 환경 설정 누락 탐지: ops_check(환경/정적/DB/마이그레이션/시드 상태 점검)

---

## 9. 확인된 전제(Assumptions)

- 운영 환경에서 DB는 PostgreSQL(Render), 로컬은 SQLite를 사용할 수 있다.
- 이미지 파일은 Cloudinary에 저장되며, DB에는 이미지 “참조값”이 저장된다.
- 방문자 기능은 읽기 전용이며, 글 작성/편집은 Admin만 가능하다.

---

## 10. 다음 변경 시 이 문서 갱신 포인트

아래가 바뀌면 이 문서를 업데이트한다.
- URL 구조(국가/카테고리/slug 라우팅)
- 모델 확장(City/Region/Tags/Series 등)
- 배포 구조(Render 이외로 변경, CDN/캐싱 추가)
- 콘텐츠 권한(로그인/댓글/커뮤니티 기능 도입)
EOF
