# Runbook: fix_slug_history

## 목적
PostSlugHistory에서 잘못된 old_slug / 충돌 / 중복(불필요) 레코드를 안전하게 정리한다.

## 원칙
- 기본은 dry-run
- 실제 삭제는 --apply로만 수행
- 적용 후 audit_content로 재검증

## Dry-run
- python manage.py fix_slug_history
- python manage.py fix_slug_history --verbose --sample 50

## Apply
- python manage.py fix_slug_history --apply

## 적용 후 검증(필수)
- python manage.py audit_content --verbose --sample 50
