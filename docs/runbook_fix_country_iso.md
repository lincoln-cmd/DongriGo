# Runbook: fix_country_iso 운영 절차

## 목적
Country의 ISO 코드(iso_a2/iso_a3) 정합성을 점검/정리하기 위한 운영 커맨드 실행 절차를 표준화한다.

## 원칙(필수)
- 기본은 항상 **dry-run**으로 실행한다.
- 출력 결과를 검토한 뒤에만 `--apply`로 실제 반영한다.
- 적용 작업은 작은 단위로 진행하고, 적용 전후에 audit로 검증한다.

---

## 1) 사전 준비 체크리스트
- [ ] 현재 배포(main) 기준점 확인
- [ ] DB 백업 정책 확인(운영 환경에서는 최소한 백업/스냅샷 확인)
- [ ] 실행 직전 `audit_content`로 현재 상태 기록

### 배포 기준점 확인(로컬)
PowerShell:
- `git fetch origin --tags`
- `git switch main`
- `git pull`
- `git describe --tags --always`

---

## 2) 로컬에서 dry-run
- `python manage.py fix_country_iso`

### 기대 동작
- 변경 예정 항목이 목록으로 출력됨
- DB는 변경되지 않음

---

## 3) 운영(Render)에서 dry-run
Render shell:
- `python manage.py fix_country_iso`

### 결과 기록
- 출력 로그를 그대로 저장(이슈/보고서/노션에 첨부)

---

## 4) 적용 전 최종 확인
- [ ] dry-run 출력에서 변경 대상이 예상과 일치하는가
- [ ] iso_a2/iso_a3 규칙 위반(길이/대문자/빈값 등)이 맞게 잡혔는가
- [ ] 적용 범위가 과도하지 않은가(예: 예상보다 너무 많은 변경)

---

## 5) 적용(--apply)
로컬 또는 Render shell에서(운영은 가급적 Render에서 단일 실행 권장):

- `python manage.py fix_country_iso --apply`

---

## 6) 적용 후 검증(필수)
- `python manage.py audit_content --verbose --sample 50`

성공 기준:
- Country ISO 관련 이슈가 감소/해결되었고,
- 예상치 못한 부작용(누락/중복)이 없어야 한다.

---

## 7) 문제 발생 시 롤백/복구
### 코드/배포 롤백(필요 시)
- GitHub에서 PR revert 또는 이전 스냅샷 태그로 복귀

### 로컬 코드 강제 동기화(표준)
- `git fetch origin`
- `git switch main`
- `git reset --hard origin/main`
- `git clean -fd`

### 데이터 롤백
- 운영 DB 백업/스냅샷 정책에 따라 복구한다.
- 적용 전 dry-run 출력 및 적용 후 audit 출력이 복구 판단의 근거가 된다.

---

## 8) 운영 메모
- `fix_country_iso`는 데이터 변경을 수행할 수 있으므로, 항상 변경 로그를 남긴다.
- 적용 작업 후에는 스냅샷 태그로 기준점을 고정한다.
