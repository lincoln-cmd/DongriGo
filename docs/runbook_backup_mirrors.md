# Runbook: GitLab/Bitbucket 수동 백업(미러 대체)

## 목적
- GitHub(origin)의 “검증된 기준점”을 수동으로 백업한다.
- 자동 미러링(매 push마다) 대신, 안전한 타이밍에만 수행한다.
- GitLab은 main 보호(Protected Branch)로 force push가 불가하므로,
  날짜 기반 backup 브랜치로 GitHub main을 보관한다.

## 백업 타이밍(원칙)
- merge → Render 배포 완료 → 스모크 테스트 완료 → snapshot 태그 생성/푸시 완료 직후
- 추가로 권장하는 시점:
  - 마이그레이션/라우팅/CI 변경 등 큰 변경이 포함된 배포 직후
  - 대형 리팩터링 착수 직전

## 원격(remote) 전제
- origin = GitHub
- gitlab = GitLab
- bitbucket = Bitbucket
- 확인:
  - git remote -v

## 표준 백업 절차(PowerShell)
### 0) GitHub main 최신화
- 로컬에서 실행:
  - git switch main
  - git fetch origin --prune --tags
  - git pull --ff-only

### 1) Bitbucket: main + tags 동기화
- Bitbucket은 main을 GitHub main과 동일하게 유지한다.
  - git push bitbucket origin/main:main
  - git push bitbucket --tags

### 2) GitLab: backup 브랜치로 GitHub main 보관 + tags 동기화
- GitLab은 main이 보호될 수 있으므로 backup 브랜치를 사용한다.
  - $stamp = Get-Date -Format "yyyy-MM-dd"
  - git push gitlab origin/main:refs/heads/backup/github-main-$stamp
  - git push gitlab --tags

### 3) 확인(필수)
- Bitbucket main이 origin/main과 같은지:
  - git ls-remote --heads bitbucket main
  - git ls-remote --heads origin main
  - 해시가 동일하면 OK
- GitLab backup 브랜치가 생성됐는지:
  - git ls-remote --heads gitlab "backup/github-main-$stamp"
- snapshot 태그가 양쪽에 존재하는지:
  - git ls-remote --tags bitbucket "snapshot/*"
  - git ls-remote --tags gitlab "snapshot/*"

## 주의사항
- GitLab에서 MR(merge request) 생성 링크가 떠도 정상이다.
  - backup 브랜치는 보관 목적이므로 MR을 만들 필요 없다.
- GitLab main을 강제 동기화하려면:
  - Protected Branch 정책 변경이 필요하며 실수 리스크가 있으므로 기본 정책은 “하지 않음”.

## 기록(운영 로그)
- 백업 수행 날짜
- 기준 snapshot 태그명
- Bitbucket main 해시
- GitLab backup 브랜치명
을 운영 로그(ELN/Notion)에 남긴다.
