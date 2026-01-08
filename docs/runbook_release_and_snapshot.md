# Runbook: Snapshot Tag / Release / Backup

## Snapshot Tag(기준점 고정) — 필수
언제?
- PR 머지 + Render 배포 + 스모크 테스트 완료 직후

PowerShell:
- `git fetch origin --tags`
- `git switch main`
- `git pull`
- `git tag snapshot/<topic>-YYYY-MM-DD`
- `git push origin snapshot/<topic>-YYYY-MM-DD`

확인:
- `git describe --tags --always`
- `git tag --list "snapshot/*" --sort=-creatordate | Select-Object -First 10`

## GitHub Release — 선택
언제?
- 기능 묶음(Phase) 마감처럼 “배포 단위”를 사용자/운영 관점에서 명확히 해야 할 때

권장:
- Release title에 snapshot 태그 포함

## GitLab/Bitbucket 백업 — 가끔만
원칙:
- 너무 자주 하지 않음(Phase 단위 종료 또는 위험 변경 직후에만)

예시:
- `git push gitlab main`
- `git push bitbucket main`
- `git push gitlab --tags`
- `git push bitbucket --tags`

## 롤백
- GitHub에서 PR revert(가장 안전) 또는 이전 snapshot 태그로 복귀
- 로컬 코드 강제 정렬:
  - `git fetch origin && git switch main && git reset --hard origin/main && git clean -fd`
- 데이터 롤백은 운영 DB 백업/스냅샷 정책에 따른다.
