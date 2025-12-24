from __future__ import annotations

import hashlib
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class Command(BaseCommand):
    help = "Load production seed fixture safely. Default fixture: fixtures/prod_seed.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture",
            default="fixtures/prod_seed.json",
            help="Fixture path (default: fixtures/prod_seed.json)",
        )
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete blog tables (PostImage/Post/Country) before loading fixture",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Load fixture even if seed has already been applied (NOT recommended on prod unless you know what you're doing)",
        )

    def handle(self, *args, **options):
        fixture = options["fixture"]
        wipe = bool(options["wipe"])
        force = bool(options["force"])

        base_dir = Path.cwd()
        fixture_path = (base_dir / fixture).resolve()

        if not fixture_path.exists():
            raise CommandError(f"Fixture not found: {fixture_path}")

        # Lazy import (Django setup 이후)
        from apps.blog.models import Country, Post, PostImage, SeedMeta  # noqa

        # ----
        # SeedMeta 기반 '멱등성' 체크
        # ----
        fixture_hash = _sha256_file(fixture_path)

        meta, _created = SeedMeta.objects.get_or_create(name="prod_seed")
        prev_hash = (meta.fixture_sha256 or "").strip()

        has_any = Country.objects.exists() or Post.objects.exists() or PostImage.objects.exists()

        if prev_hash:
            if prev_hash == fixture_hash:
                if not wipe and not force:
                    self.stdout.write(self.style.SUCCESS("Seed skipped: same fixture already applied (hash match)."))
                    return
                if force and not wipe:
                    self.stdout.write(self.style.WARNING("Re-applying the same fixture due to --force (usually unnecessary)."))
            else:
                # 다른 fixture가 적용되어 있었음 → 운영 사고 방지를 위해 기본은 차단
                if not wipe and not force:
                    raise CommandError(
                        "Seed blocked: fixture differs from previously applied seed.\n"
                        f"- previous sha256: {prev_hash}\n"
                        f"- current  sha256: {fixture_hash}\n"
                        "Run with --wipe to reset and apply the new fixture. "
                        "(You can override with --force, but it may create duplicates.)"
                    )
                if force and not wipe:
                    self.stdout.write(
                        self.style.WARNING(
                            "WARNING: Applying a different fixture due to --force WITHOUT --wipe. "
                            "This can create duplicates or inconsistent data. Prefer --wipe."
                        )
                    )
        else:
            # SeedMeta가 비어있지만 데이터가 이미 있으면(운영에서 흔한 실수) 기본은 스킵
            if has_any and not wipe and not force:
                self.stdout.write(
                    self.style.WARNING(
                        "Seed skipped: blog tables already have data but no SeedMeta exists yet.\n"
                        "Use --wipe to reset, or --force to proceed anyway."
                    )
                )
                return

        # ----
        # Wipe (예측 가능한 초기화)
        # ----
        if wipe:
            self.stdout.write(self.style.WARNING("Wiping blog tables: PostImage -> Post -> Country"))
            PostImage.objects.all().delete()
            Post.objects.all().delete()
            Country.objects.all().delete()

        # ----
        # Load fixture
        # ----
        self.stdout.write(self.style.SUCCESS(f"Loading fixture: {fixture_path}"))
        call_command("loaddata", str(fixture_path))

        # ----
        # Phase 1-Step 1: 정합성 점검/보수적 정규화(자동 수정은 안전 범위만)
        # ----
        try:
            self.stdout.write(self.style.WARNING("Running integrity check (--fix)..."))
            call_command("check_integrity", "--fix")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Integrity check failed (seed continues): {e}"))

        # ----
        # SeedMeta 기록(멱등성 보장용)
        # ----
        meta.fixture_path = str(fixture)
        meta.fixture_sha256 = fixture_hash
        meta.applied_at = timezone.now()
        meta.notes = {
            "countries": Country.objects.count(),
            "posts": Post.objects.count(),
            "post_images": PostImage.objects.count(),
        }
        meta.save(update_fields=["fixture_path", "fixture_sha256", "applied_at", "notes"])

        self.stdout.write(self.style.SUCCESS("Seed finished OK."))
