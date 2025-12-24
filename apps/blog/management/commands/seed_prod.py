from __future__ import annotations

from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


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
            help="Load fixture even if data already exists",
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
        from apps.blog.models import Country, Post, PostImage  # noqa

        # 현재 데이터 존재 여부
        has_any = Country.objects.exists() or Post.objects.exists() or PostImage.objects.exists()

        if has_any and not force and not wipe:
            self.stdout.write(
                self.style.WARNING(
                    "Seed skipped: blog tables already have data. "
                    "Use --force to load anyway, or --wipe to clear first."
                )
            )
            return

        if wipe:
            self.stdout.write(self.style.WARNING("Wiping blog tables: PostImage -> Post -> Country"))
            PostImage.objects.all().delete()
            Post.objects.all().delete()
            Country.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(f"Loading fixture: {fixture_path}"))
        call_command("loaddata", str(fixture_path))

        # ✅ Phase 1: 로드 후 정합성 점검/보수적 정규화(자동 수정은 안전 범위만)
        # - iso 대문자/공백 정리, "" -> NULL 정규화, slug 누락 채우기 등
        # - check_integrity 커맨드를 아직 추가하지 않았다면 에러만 출력하고 seed는 계속 진행
        try:
            self.stdout.write(self.style.WARNING("Running integrity check (--fix)..."))
            call_command("check_integrity", "--fix")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Integrity check failed (seed continues): {e}"))

        self.stdout.write(self.style.SUCCESS("Seed finished OK."))
