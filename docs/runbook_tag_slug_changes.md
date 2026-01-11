# Runbook: Tag slug 변경 운영 절차 (TagSlugHistory + Redirect)

## 목적
- Tag slug가 변경되더라도 기존 주소(/tags/<old>/)가 깨지지 않게 유지한다.
- old slug로 접근 시 canonical slug(/tags/<new>/)로 리다이렉트된다.
- HTMX 요청에서도 보드 UX를 유지한다(204 + HX-Redirect).

## 사전 조건
- 배포는 GitHub main merge 이후 Render 자동 배포로 진행한다.
- 배포 후 스모크 테스트 및 snapshot 태그를 반드시 남긴다.

## 핵심 동작(정의)
- Tag slug 변경 시, 시스템은 old slug를 TagSlugHistory로 보존한다.
- /tags/<old>/ 접근:
  - 일반 요청: 301 → /tags/<new>/ (쿼리스트링 유지)
  - HTMX 요청: 204 + HX-Redirect: /tags/<new>/ (쿼리스트링 유지)
- Unicode slug(예: 온천)도 지원하며, 헤더/Location은 ASCII(퍼센트 인코딩) 형태로 정규화된다.

## 변경 방법(권장)
### A) Django admin에서 변경
1. Admin에서 Tag 선택
2. slug 변경(필요 시 name도 함께 정합성 맞춤)
3. 저장 후 확인:
   - TagSlugHistory에 old_slug 기록이 생성되어야 한다(자동 생성 로직이 있는 경우)
   - (가능하면) old slug로 접근 시 리다이렉트되는지 확인

### B) 운영 DB에서 직접 수정 금지(원칙)
- 운영 DB 직접 UPDATE로 slug를 바꾸는 것은 지양한다.
- 반드시 admin 또는 검증된 관리 커맨드를 통해 변경한다.

## 배포 전 체크(로컬)
- 테스트:
  - python manage.py test
- 콘텐츠 감사(선택/권장):
  - python manage.py audit_content --verbose --sample 50

## 배포 후 체크(운영, 스모크)
1. 태그 인덱스:
   - /tags/ 200 OK
2. canonical slug:
   - /tags/<new>/ 200 OK
3. old slug 리다이렉트(데이터가 존재하는 경우에만 검증 가능):
   - /tags/<old>/ → /tags/<new>/ 301 OK
   - 쿼리스트링 유지 확인: ?q=x&page=2&sort=old 등
4. HTMX 동작(가능하면):
   - 태그 보드에서 이동/로딩 정상
   - old slug가 존재하면 204 + HX-Redirect 동작
5. Render shell(권장):
   - python manage.py audit_content --verbose --sample 50
   - issues 0 ✅ 확인

## 문제 발생 시(트러블슈팅)
### 1) old slug 접근이 404
- TagSlugHistory에 해당 old_slug가 존재하는지 확인
- 존재하지 않으면:
  - slug 변경이 admin 외부에서 발생했거나, history 생성 로직이 누락됐을 가능성
- 우선 조치:
  - 최근 변경 내역/커밋 확인
  - 필요하면 hotfix로 history 생성 로직 보완 후 재배포

### 2) Unicode slug에서 Location/HX-Redirect가 깨짐
- 헤더/리다이렉트 URL이 iri_to_uri 기준으로 정규화되는지 확인
- 테스트가 이를 고정하고 있어야 한다(회귀 방지)

## 롤백
- 원칙: “배포/스모크 완료한 snapshot 태그” 단위로 롤백 판단
- 방법:
  - GitHub에서 해당 PR revert → merge → Render 자동 배포 → 스모크
  - 또는 직전 snapshot 태그 기준으로 상태 복구(필요 시)

## 기록(운영 로그)
- slug 변경을 수행한 날짜/대상 Tag/old→new를 운영 로그(ELN/Notion)에 남긴다.
