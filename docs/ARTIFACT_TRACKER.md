# DongriGo – Project Artifact Tracker (v1.0)

- 기준: “웹 개발 프로세스 및 산출물 정리(1)” 흐름에 맞춰 **Phase 단위 + 필수 산출물**을 관리
- 상태 표기: [ ] 예정  [~] 진행중  [x] 완료
- 산출물은 원칙적으로 `docs/` 아래에 보관 (운영 절차/코드 커맨드는 README에도 요약)
- `./Lessons Learned` 하위에는 '오류 공유 보고서', '실패 원인 분석 보고서' 등만 따로 관리

---

## Phase 0 — Baseline
### 0.1 프로젝트 개요/범위
- [x] 프로젝트 개요(README 상단, 목적/정책/범위)
- [x] 배포 주소/관리자 주소/운영 스택 명시(README)
- [ ] PRD(간단 버전, 1~2p): 기능 범위/비범위/성공 기준  
  - 파일: `docs/phase0/PRD.md`

### 0.2 아키텍처/구성요소
- [ ] 시스템 아키텍처 1페이지(다이어그램 + 설명 10줄)
  - 파일: `docs/phase0/ARCHITECTURE.md`
  - 시각화: `docs/phase0/architecture.png` (또는 mermaid)
- [x] 데이터 모델 요약(Country/Post/PostImage + SeedMeta/SlugHistory) *(README/코드 기반)*  
- [ ] URL/라우팅 규칙 문서(국가/카테고리/slug)
  - 파일: `docs/phase0/ROUTING.md`

### 0.3 핵심 UX/콘텐츠 작성 흐름
- [x] Admin 기반 작성 정책(관리자만 작성, 방문자는 읽기 전용) *(README)*
- [x] 이미지 토큰([[img:ID]]) 워크플로우 *(기능 존재, 문서 보강 권장)*
- [ ] Admin 작성 가이드(스크린샷 포함, 1~2p)
  - 파일: `docs/phase0/ADMIN_WORKFLOW.md`
  - 시각화: `docs/phase0/admin_workflow.png` (스크린샷)

---

## Phase 1 — 데이터/운영 안정화 (완료 목표: 운영 사고 예방)
### 1.1 데이터 정합성 규칙/검사
- [x] `check_integrity` 커맨드 구현 및 출력(JSON) 확인
- [ ] 정합성 규칙 스펙(무엇을 검사/수정하는지 명시)
  - 파일: `docs/phase1/DATA_INTEGRITY_SPEC.md`
- [ ] 정합성 검사 결과 로그 템플릿(예시 JSON 첨부)
  - 파일: `docs/phase1/integrity_report_sample.json`

### 1.2 시딩/Fixture 멱등성
- [x] SeedMeta 도입(해시 기반 스킵) + 운영에서 동작 확인
- [ ] 시딩 정책 문서(--wipe/--force 의미, 운영 권장 시나리오)
  - 파일: `docs/phase1/SEEDING_POLICY.md`

### 1.3 Slug 정책 + 링크 보존
- [x] SlugHistory 도입 + 예전 URL 301 redirect 확인
- [ ] slug 정책 문서(중복 처리, 변경 시 행동, 리다이렉트 범위)
  - 파일: `docs/phase1/SLUG_POLICY.md`

### 1.4 Admin 검증/경고 표시
- [x] Country/Post Admin에 경고/정규화/메시지 반영
- [ ] Admin 검증 규칙 문서(ISO/aliases/published_at/slug_history)
  - 파일: `docs/phase1/ADMIN_VALIDATION_RULES.md`

### 1.5 운영 점검(런북/진단)
- [x] `ops_check` 커맨드 구현(로컬 확인 완료)
- [ ] 운영(Render)에서 ops_check 동작 확인 로그(출력 캡처/JSON 보관)
  - 파일: `docs/phase1/ops_check_render.json`
- [x] README에 Ops Runbook 추가(명령어 블록)

**Phase 1 Exit Criteria (완료 조건)**
- [x] 운영(Render)에서 seed_prod 멱등 스킵 동작
- [x] slug 변경 리다이렉트 동작
- [x] admin 목록에서 check 컬럼 정상 표시
- [ ] 운영(Render)에서 `ops_check --json` 실행 성공 로그 보관(권장)

---

## Phase 2 — UX 개선 (방문자/관리자 체감)
### 2.1 로딩/빈 상태/실패 상태 UI
- [ ] 국가 클릭 로딩 스켈레톤/indicator
- [ ] “해당 국가 콘텐츠 없음” 빈 상태
- [ ] HTMX 실패 시 에러 메시지 + 재시도
- 산출물:
  - [ ] UX 변경 요약(전/후 스크린샷 2장)
    - 파일: `docs/phase2/UX_IMPROVEMENTS_01.md`
    - 시각화: `docs/phase2/ux_before_after_01.png`

### 2.2 검색 UX 강화
- [ ] 빈 결과 메시지/하이라이트
- [ ] (선택) 자동완성/최근 검색
- 산출물:
  - [ ] 검색 UX 문서 + 테스트 케이스
    - 파일: `docs/phase2/SEARCH_UX.md`

### 2.3 반응형/모바일 최적화
- [ ] 보드 레이아웃/터치 UX 개선
- 산출물:
  - [ ] 반응형 체크리스트 + 주요 화면 스크린샷
    - 파일: `docs/phase2/RESPONSIVE_CHECKLIST.md`

---

## Phase 3 — 기능 확장 (모델 확장)
- [ ] City/Region 모델 설계/마이그레이션/관리 화면
- [ ] 태그 시스템(필터/페이지)
- [ ] 시리즈/TOC 자동 생성
- 산출물:
  - [ ] ERD 업데이트 + 마이그레이션 로그
    - 파일: `docs/phase3/ERD.md`

---

## Phase 4 — 계정/커뮤니티 (선택)
- [ ] 댓글/모더레이션/스팸 방지
- [ ] 로그인/소셜 로그인
- 산출물:
  - [ ] Threat Model(간단)
    - 파일: `docs/phase4/THREAT_MODEL.md`

---

## Phase 5 — 운영/성능/SEO (장기)
- [ ] sitemap/robots/OG 고도화
- [ ] 캐싱/이미지 최적화/CDN
- [ ] Sentry 등 관측성 + 백업/복구 문서
- 산출물:
  - [ ] 성능/SEO 리포트(전/후 측정)
    - 파일: `docs/phase5/PERF_SEO_REPORT.md`
  - [ ] 백업/복구 Runbook
    - 파일: `docs/phase5/BACKUP_RECOVERY.md`

---

## Quick Links (프로젝트 핵심 진입점)
- Site: https://dongrigo.onrender.com
- Admin: https://dongrigo.onrender.com/admin
- Key Commands:
  - `python manage.py seed_prod`
  - `python manage.py check_integrity --fix --json`
  - `python manage.py ops_check --json`
