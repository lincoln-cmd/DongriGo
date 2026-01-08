from __future__ import annotations

from typing import Iterable

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Exists, OuterRef

from apps.blog.models import Post, PostSlugHistory


# Django validate_slug 기준(ASCII slug). 현재 운영에서 'ᄉ' 같은 값이 걸리는 케이스 대응.
VALID_SLUG_REGEX = r"^[-a-zA-Z0-9_]+$"


def _print(lines: Iterable[str]) -> None:
    for line in lines:
        print(line)


class Command(BaseCommand):
    help = (
        "Fix PostSlugHistory issues in a safe way.\n"
        "- Default: dry-run (no DB change)\n"
        "- Use --apply to delete problematic rows\n"
        "Targets:\n"
        "  1) invalid old_slug (not matching Django slug regex)\n"
        "  2) collisions: old_slug matches another Post.slug for same (country, category)\n"
        "  3) redundant: old_slug equals current slug of the same post in same (country, category)\n"
        "  4) orphan rows (post missing) if exist (DB-level anomalies)\n"
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Actually delete rows (default: dry-run).")
        parser.add_argument("--verbose", action="store_true", help="Print sample rows for each category.")
        parser.add_argument("--sample", type=int, default=50, help="Max sample rows to print for each category.")

    def handle(self, *args, **options):
        apply: bool = bool(options.get("apply"))
        verbose: bool = bool(options.get("verbose"))
        sample: int = int(options.get("sample") or 50)

        lines: list[str] = []
        lines.append("=== Fix PostSlugHistory (safe) ===")
        lines.append(f"- mode: {'APPLY' if apply else 'DRY-RUN'}")

        base_qs = PostSlugHistory.objects.all()
        total = base_qs.count()
        lines.append(f"- total rows: {total}")

        # 1) invalid old_slug
        invalid_slug_qs = base_qs.exclude(old_slug__regex=VALID_SLUG_REGEX)
        invalid_slug_ids = list(invalid_slug_qs.values_list("id", flat=True))

        # 2) orphan rows (post missing) - should not happen on Postgres FK, but can exist if legacy/SQLite anomalies
        orphan_qs = base_qs.annotate(
            has_post=Exists(Post.objects.filter(id=OuterRef("post_id")))
        ).filter(has_post=False)
        orphan_ids = list(orphan_qs.values_list("id", flat=True))

        # 3) collisions with current slugs for same (country, category)
        collision_qs = base_qs.annotate(
            collides=Exists(
                Post.objects.filter(
                    country_id=OuterRef("country_id"),
                    category=OuterRef("category"),
                    slug=OuterRef("old_slug"),
                ).exclude(id=OuterRef("post_id"))
            )
        ).filter(collides=True)
        collision_ids = list(collision_qs.values_list("id", flat=True))

        # 4) redundant rows: old_slug equals current slug of the same post in same (country, category)
        redundant_ids: list[int] = []
        # join을 쓰면 orphan row가 빠질 수 있으니(이미 orphan은 별도 탐지), 여기서는 post가 있는 row 위주로만 확인
        for h in PostSlugHistory.objects.select_related("post").all():
            p = getattr(h, "post", None)
            if not p:
                continue
            if h.country_id == p.country_id and h.category == p.category and h.old_slug == p.slug:
                redundant_ids.append(h.id)

        # final delete set
        to_delete = sorted(set(invalid_slug_ids) | set(orphan_ids) | set(collision_ids) | set(redundant_ids))
        lines.append(f"- invalid old_slug: {len(invalid_slug_ids)}")
        lines.append(f"- orphan rows: {len(orphan_ids)}")
        lines.append(f"- collisions with current slugs: {len(collision_ids)}")
        lines.append(f"- redundant rows: {len(redundant_ids)}")
        lines.append(f"- to delete: {len(to_delete)}")

        if verbose and to_delete:
            lines.append("\n[Samples]")
            # 최대 sample만 출력
            for h in PostSlugHistory.objects.filter(id__in=to_delete).select_related("country")[:sample]:
                lines.append(
                    f"  ! id={h.id} country_id={h.country_id} category={h.category} old_slug='{h.old_slug}' post_id={h.post_id}"
                )

        _print(lines)

        if not to_delete:
            self.stdout.write(self.style.SUCCESS("No rows to fix."))
            return

        if not apply:
            self.stderr.write(self.style.ERROR("Found problematic rows. Run with --apply to delete them."))
            raise SystemExit(1)

        with transaction.atomic():
            deleted_count, _ = PostSlugHistory.objects.filter(id__in=to_delete).delete()

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_count} PostSlugHistory rows."))

        # After apply, re-check quickly
        remaining_issues = PostSlugHistory.objects.exclude(old_slug__regex=VALID_SLUG_REGEX).count()
        if remaining_issues:
            self.stderr.write(self.style.ERROR("Some invalid-slug rows still remain after apply."))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("Fix completed."))
        return
