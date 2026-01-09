# Runbook: audit_content

## 목적
운영/로컬 DB의 콘텐츠 정합성을 **읽기 전용(read-only)** 으로 점검한다.
- Country / Tag / Post / PostSlugHistory의 대표적인 무결성 이슈를 탐지
- DB를 **절대 변경하지 않음**

## 핵심 원칙
- 기본은 `audit_content`로 **현상 파악 → 로그 저장 → 원인/조치 결정**
- 데이터 변경이 필요한 경우에만 별도 커맨드(`fix_* --apply`)를 실행
- `audit_content`는 **이슈가 있으면 종료 코드 1**로 끝난다(= CI/자동점검에서 실패로 취급 가능)

---

## 언제 실행하나
- Render 배포 직후 1회(권장)
- 운영 데이터 변경 커맨드 실행 전/후
  - 예: `fix_country_iso --apply`, `fix_slug_history --apply`
- 태그/slug/리다이렉트 관련 이슈 수정 후 회귀 점검

---

## 실행 (로컬)
기본:
```bash
python manage.py audit_content
