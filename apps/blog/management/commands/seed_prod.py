from __future__ import annotations

import os
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

        # 사후 검증(iso_a2 2글자 제한 같은 사고 재발 방지)
        bad_iso2 = list(Country.objects.exclude(iso_a2__isnull=True).exclude(iso_a2="").extra(
            where=["length(iso_a2) > 2"]
        ).values_list("id", "name", "iso_a2")[:20])

        if bad_iso2:
            self.stdout.write(self.style.ERROR("WARNING: Found iso_a2 longer than 2 chars (showing up to 20):"))
            for row in bad_iso2:
                self.stdout.write(f"- {row}")
            self.stdout.write(self.style.ERROR("Fix these rows, then rebuild fixture with rebuild_seed."))
        else:
            self.stdout.write(self.style.SUCCESS("Seed finished OK."))
