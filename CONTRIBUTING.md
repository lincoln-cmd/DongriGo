# Contributing (DongriGo)

## 원칙(최우선)
- main 직접 작업 금지(머지/태그/릴리즈 기준점 관리만)
- 모든 변경은 새 브랜치에서 진행
- PR 머지 전: CI(test) 통과 필수 + 불변 조건(HTMX Doc 0 등) 유지
- 머지 후: Render 배포 확인 + 스모크 + 스냅샷 태그로 기준점 고정

## 작업 시작(항상)
PowerShell:
- `git fetch origin --tags`
- `git switch main`
- `git pull`
- `git log -1 --oneline --decorate`
- `git describe --tags --always`

## 브랜치 생성(필수)
예: `feat/...`, `fix/...`, `ui/...`, `ops/...`, `docs/...`, `ci/...`
- `git switch -c <type>/<topic>`

## 로컬 테스트(최소)
- `python manage.py test`
- 브라우저 스모크(필수 불변조건):
  - 홈 로드 OK
  - 국가 클릭 → 보드 로드 OK
  - 보드 내 이동 중 Network Document(Doc) 요청 = 0 (fetch/xhr만)

## 커밋/푸시
- `git add -A`
- `git commit -m "<type>(scope): message"`
- `git push -u origin HEAD`

## PR → 머지
- PR 템플릿 체크리스트를 채운다(불변 조건/테스트/롤백/스냅샷).
- Branch protection으로 CI(test) 통과 전 머지 불가.

## 머지 후(필수)
- Render 배포 성공 확인
- 스모크 테스트(최소):
  - 홈/국가 클릭/보드 Doc 0
- 스냅샷 태그 생성 및 푸시(기준점 고정)
  - `git switch main`
  - `git pull`
  - `git tag snapshot/<topic>-YYYY-MM-DD`
  - `git push origin snapshot/<topic>-YYYY-MM-DD`

## 긴급 복구(표준)
- `git fetch origin`
- `git switch main`
- `git reset --hard origin/main`
- `git clean -fd`
