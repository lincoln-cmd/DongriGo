from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.blog.models import Tag, TagSlugAlias


def slugify_ko_safe(name: str) -> str:
    # 보수적: 한글이면 slug로 그대로 쓰기(유니코드 slug 허용) + 공백/슬래시만 간단 정리
    s = (name or "").strip()
    s = s.replace(" ", "-").replace("/", "-")
    # 연속 하이픈 정리
    while "--" in s:
        s = s.replace("--", "-")
    return s


class Command(BaseCommand):
    help = (
        "Normalize Tag.slug safely.\n"
        "- default: dry-run\n"
        "- use --apply to update Tag.slug and create TagSlugAlias(old_slug)\n"
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run).")
        parser.add_argument("--verbose", action="store_true", help="Print per-row details.")
        parser.add_argument("--sample", type=int, default=50, help="Max rows to show.")

    def handle(self, *args, **opts):
        apply = bool(opts.get("apply"))
        verbose = bool(opts.get("verbose"))
        sample = int(opts.get("sample") or 50)

        # 정책: name 기반 기대 slug
        # - 한글 이름은 유니코드 slug 허용(현재 audit 기대값이 name 자체인 것으로 보임)
        # - 영문/숫자 등은 현재 slug 유지(이미 정상 데이터 다수)
        candidates = []
        for t in Tag.objects.all().order_by("id"):
            expected = slugify_ko_safe(t.name)
            if not expected:
                continue
            if t.slug != expected:
                candidates.append((t, expected))

        self.stdout.write("=== Fix Tag slugs (safe) ===")
        self.stdout.write(f"- mode: {'APPLY' if apply else 'DRY-RUN'}")
        self.stdout.write(f"- candidates: {len(candidates)}")

        if not candidates:
            self.stdout.write(self.style.SUCCESS("No tag slugs to normalize."))
            return

        shown = 0
        for t, expected in candidates:
            if shown < sample:
                self.stdout.write(f"  - tag_id={t.id} name='{t.name}' slug='{t.slug}' -> expected='{expected}'")
                shown += 1

        if not apply:
            self.stderr.write(self.style.ERROR("Run with --apply to create aliases and update slugs."))
            raise SystemExit(1)

        with transaction.atomic():
            for t, expected in candidates:
                # 충돌 방지: expected slug가 이미 Tag.slug로 존재하면 스킵(또는 suffix 정책 필요)
                if Tag.objects.exclude(id=t.id).filter(slug=expected).exists():
                    self.stderr.write(
                        self.style.WARNING(f"SKIP tag_id={t.id}: expected slug '{expected}' already exists.")
                    )
                    continue

                # alias 충돌 방지(uniqueness)
                if TagSlugAlias.objects.filter(old_slug=t.slug).exists():
                    self.stderr.write(
                        self.style.WARNING(f"SKIP tag_id={t.id}: alias old_slug '{t.slug}' already exists.")
                    )
                    continue

                TagSlugAlias.objects.create(tag=t, old_slug=t.slug)
                t.slug = expected
                t.save(update_fields=["slug"])

        self.stdout.write(self.style.SUCCESS("Tag slug normalization completed."))
