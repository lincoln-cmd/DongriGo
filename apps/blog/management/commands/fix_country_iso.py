from __future__ import annotations

import re
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.blog.models import Country


ISO_A3_RE = re.compile(r"^[A-Za-z]{3}$")


class Command(BaseCommand):
    help = "Fix invalid Country.iso_a3 values. Default is dry-run; use --apply to write changes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes to DB (otherwise dry-run).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Max rows to print in output (default 200).",
        )

    def handle(self, *args, **options):
        apply: bool = bool(options.get("apply"))
        limit: int = int(options.get("limit") or 200)

        qs = Country.objects.all().only("id", "slug", "name", "iso_a3")
        bad = []
        for c in qs.iterator():
            val = (getattr(c, "iso_a3", None) or "").strip()
            if val == "":
                continue
            if not ISO_A3_RE.match(val):
                bad.append((c.id, c.slug, getattr(c, "name", ""), val))

        if not bad:
            self.stdout.write(self.style.SUCCESS("No invalid iso_a3 values found."))
            return

        self.stdout.write(f"Found {len(bad)} invalid iso_a3 values.")
        for row in bad[:limit]:
            self.stdout.write(f"- id={row[0]} slug={row[1]} name={row[2]} iso_a3='{row[3]}'")
        if len(bad) > limit:
            self.stdout.write(f"... (truncated, showing first {limit})")

        if not apply:
            self.stdout.write(self.style.WARNING("Dry-run only. Use --apply to fix."))
            # non-zero so CI/ops can catch that there are pending fixes if desired
            raise SystemExit(1)

        with transaction.atomic():
            ids = [r[0] for r in bad]
            # 보수적 처리: invalid 값은 빈 값으로 정리
            updated = Country.objects.filter(id__in=ids).update(iso_a3=None)
        self.stdout.write(self.style.SUCCESS(f"Applied: cleared iso_a3 for {updated} countries."))
        return
