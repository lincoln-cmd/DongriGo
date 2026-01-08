## PR 요약
- 무엇을/왜 변경했는지 3~5줄로 요약

## 변경 범위
- 변경 파일:
- 영향 범위(템플릿/JS/CSS/모델/커맨드/문서):

## 불변 조건 체크(필수)
- [ ] 보드 내 이동 중 Network Document(Doc) 요청 = 0 (fetch/xhr만)
- [ ] `_board.html`의 data-has-* 마커 규칙 유지
- [ ] board_state.js = 보드 상태 SSOT 유지
- [ ] popstate/HTMX history restore 시 globe.js가 loadBoard()로 #boardContent 재로딩하지 않음

## 로컬 테스트(필수)
- [ ] `python manage.py test`
- [ ] 홈 로드 OK
- [ ] 지구본 렌더 OK / 국가 클릭 → 보드 로드 OK
- [ ] 보드 내 이동 몇 번 수행 후 Doc 0 확인

## Render 배포 후 스모크(머지 후 필수)
- [ ] 홈 로드 OK
- [ ] 국가 클릭 → 보드 로드 OK
- [ ] 보드 내 이동 중 Doc 0 확인
- [ ] (선택) `python manage.py audit_content` OK

## 롤백/복구
- PR revert 또는 스냅샷 태그로 복귀
- 로컬 강제 동기화:
  - `git fetch origin && git switch main && git reset --hard origin/main && git clean -fd`

## 스냅샷 태그(머지+배포+스모크 완료 후)
- [ ] `git tag snapshot/<topic>-YYYY-MM-DD && git push origin snapshot/<topic>-YYYY-MM-DD`
