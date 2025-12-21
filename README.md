# DongriGo

국가별 **역사·문화·여행 정보(가이드)**와 **개인 여행 기록(로그)**을 함께 제공하는 콘텐츠 사이트입니다.
글 작성/편집은 **관리자(Django admin)만 가능**, 방문자는 **읽기 전용**입니다.
이미지/첨부 파일은 **S3 또는 Cloudinary**에 저장합니다.

## Core Features
- 관리자 전용 콘텐츠 관리: Django admin에서 글 작성/수정/삭제
- 콘텐츠 2트랙
  - Guide: 국가별 역사/문화/여행 정보(지식형)
  - Log: 개인 여행 기록(일기/후기형)
- 탐색/정리(예정)
  - 국가/도시/태그 기반 분류
  - 목록/상세 페이지, 검색(고도화)
  - 웹/앱 구현 및 댓글 기능 추가(고도화)
  - 자체 번역 AI 기능 탑재(고도화)
  - 카테고리 중 History, Culture 부분 내 이미지 캐릭터화 및 내용 설명 AI(고도화)
- 이미지 업로드: S3 또는 Cloudinary 연동
- SEO 기본 구성(메타/OG, sitemap 등은 단계적으로)

## Content Structure
- Country (국가)
- City/Region (도시/지역)
- Post
  - type: `History` | `Culture` | `Travel` | `My Log`
  - tags: 문화/역사/맛집/교통/숙소/예산/주의사항 등
  - location: 국가/도시 연결
  - cover_image / gallery_images

## Tech Stack
- Python, Django
- Storage: AWS S3 (or S3-compatible) **or** Cloudinary
- DB: SQLite(dev) / PostgreSQL(prod 권장)
- Docker(보류), GitHub Actions(CI)

## Post Exclusion Part
- .env/SECRET_KEY가 들어간 파일
- 대용량 파일 (GeoJSON 등의 100MB가 초과하는 파일은 .gitignore로 제외될 수 있음.)
- collectstatic 결과물(staticfiles/): 배포 환경에서 다시 생성하는 게 표준이라 .gitignore로 제외
