from __future__ import annotations

from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Rebuild fixtures/prod_seed.json in UTF-8 safely (Windows encoding issues prevention)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="fixtures/prod_seed.json",
            help="Output path (default: fixtures/prod_seed.json)",
        )
        parser.add_argument(
            "--indent",
            type=int,
            default=2,
            help="JSON indent (default: 2)",
        )

    def handle(self, *args, **options):
        out = options["output"]
        indent = int(options["indent"])

        out_path = (Path.cwd() / out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # dumpdata는 stdout으로 내보낼 수 있으니,
        # 파일 핸들을 UTF-8로 열어주면 Windows에서도 charmap 문제를 피할 수 있음.
        self.stdout.write(self.style.WARNING(f"Rebuilding fixture to: {out_path} (UTF-8)"))

        with out_path.open("w", encoding="utf-8", newline="\n") as f:
            call_command(
                "dumpdata",
                "blog.Country",
                "blog.Post",
                "blog.PostImage",
                indent=indent,
                stdout=f,
            )

        self.stdout.write(self.style.SUCCESS("Fixture rebuilt OK."))
