from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


@dataclass
class CheckItem:
    key: str
    status: str  # "OK" | "WARN" | "ERROR"
    message: str
    meta: Dict[str, Any] | None = None


def _env_exists(name: str) -> bool:
    v = os.environ.get(name)
    return v is not None and str(v).strip() != ""


def _static_manifest_expected() -> bool:
    backend = ""
    try:
        backend = settings.STORAGES["staticfiles"]["BACKEND"]
    except Exception:
        backend = ""
    return "ManifestStaticFilesStorage" in backend


def _static_manifest_path() -> Path:
    static_root = Path(getattr(settings, "STATIC_ROOT", "") or "")
    return static_root / "staticfiles.json"


class Command(BaseCommand):
    help = "Operational sanity checks for production (env/static/db/migrations/seed)."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
        parser.add_argument("--strict", action="store_true", help="Exit non-zero if any ERROR is found.")

    def handle(self, *args, **options):
        as_json = bool(options["json"])
        strict = bool(options["strict"])

        items: List[CheckItem] = []

        # 1) Settings / env
        items.append(CheckItem("django.DEBUG", "OK", f"DEBUG={settings.DEBUG}"))

        if _env_exists("SECRET_KEY") or getattr(settings, "SECRET_KEY", ""):
            items.append(CheckItem("env.SECRET_KEY", "OK", "SECRET_KEY is set (value hidden)."))
        else:
            items.append(CheckItem("env.SECRET_KEY", "ERROR", "SECRET_KEY is missing."))

        allowed = list(getattr(settings, "ALLOWED_HOSTS", []) or [])
        if allowed:
            items.append(CheckItem("django.ALLOWED_HOSTS", "OK", f"{len(allowed)} host(s) configured.", {"hosts": allowed}))
        else:
            items.append(CheckItem("django.ALLOWED_HOSTS", "WARN", "ALLOWED_HOSTS is empty. DisallowedHost likely in prod."))

        if _env_exists("DATABASE_URL"):
            items.append(CheckItem("env.DATABASE_URL", "OK", "DATABASE_URL is set (value hidden)."))
        else:
            items.append(CheckItem("env.DATABASE_URL", "WARN", "DATABASE_URL not set. DB may still be configured via other settings."))

        use_cloudinary = bool(getattr(settings, "USE_CLOUDINARY", False))
        cloud_meta = {"USE_CLOUDINARY": use_cloudinary}
        if use_cloudinary:
            cred_ok = _env_exists("CLOUDINARY_URL") or (
                _env_exists("CLOUDINARY_CLOUD_NAME") and _env_exists("CLOUDINARY_API_KEY") and _env_exists("CLOUDINARY_API_SECRET")
            )
            cloud_meta.update({
                "CLOUDINARY_URL": _env_exists("CLOUDINARY_URL"),
                "CLOUDINARY_CLOUD_NAME": _env_exists("CLOUDINARY_CLOUD_NAME"),
                "CLOUDINARY_API_KEY": _env_exists("CLOUDINARY_API_KEY"),
                "CLOUDINARY_API_SECRET": _env_exists("CLOUDINARY_API_SECRET"),
            })
            items.append(CheckItem(
                "cloudinary.credentials",
                "OK" if cred_ok else "ERROR",
                "Cloudinary enabled; credentials present." if cred_ok else "Cloudinary enabled but credentials missing.",
                cloud_meta,
            ))
        else:
            items.append(CheckItem("cloudinary.enabled", "OK", "Cloudinary is disabled (local file storage).", cloud_meta))

        # 2) Static files sanity
        static_root = Path(getattr(settings, "STATIC_ROOT", "") or "")
        if static_root and static_root.exists():
            items.append(CheckItem("static.STATIC_ROOT", "OK", f"STATIC_ROOT exists: {static_root}"))
        else:
            items.append(CheckItem(
                "static.STATIC_ROOT",
                "WARN" if settings.DEBUG else "ERROR",
                f"STATIC_ROOT missing or not created: {static_root or '(empty)'}",
            ))

        if _static_manifest_expected():
            manifest = _static_manifest_path()
            if manifest.exists():
                items.append(CheckItem("static.manifest", "OK", f"Manifest present: {manifest.name}"))
            else:
                items.append(CheckItem("static.manifest", "ERROR", f"Manifest missing: {manifest}. Run collectstatic in build."))
        else:
            items.append(CheckItem("static.manifest", "OK", "Manifest not required for current staticfiles storage backend."))

        # 3) DB connectivity
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            items.append(CheckItem("db.connection", "OK", f"Connected to DB: {connection.settings_dict.get('NAME')}"))
        except OperationalError as e:
            items.append(CheckItem("db.connection", "ERROR", "DB connection failed.", {"error": str(e)}))

        # 4) Migrations
        try:
            from django.db.migrations.executor import MigrationExecutor
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                items.append(CheckItem(
                    "db.migrations",
                    "WARN" if settings.DEBUG else "ERROR",
                    f"{len(plan)} unapplied migration(s).",
                    {"count": len(plan), "sample": [f"{m.app_label}.{m.name}" for m, _ in plan[:10]]},
                ))
            else:
                items.append(CheckItem("db.migrations", "OK", "No unapplied migrations."))
        except Exception as e:
            items.append(CheckItem("db.migrations", "WARN", "Could not evaluate migration plan.", {"error": str(e)}))

        # 5) Seed safety (SeedMeta)
        try:
            from apps.blog.models import SeedMeta  # type: ignore
            meta = SeedMeta.objects.filter(name="prod_seed").first()
            if meta and (meta.fixture_sha256 or "").strip():
                items.append(CheckItem(
                    "seed.meta",
                    "OK",
                    "SeedMeta present; idempotent seeding is active.",
                    {"fixture_path": meta.fixture_path, "sha256": meta.fixture_sha256[:12] + "...", "applied_at": str(meta.applied_at)},
                ))
            else:
                items.append(CheckItem("seed.meta", "WARN", "SeedMeta not found or missing sha256. Seeding safety may be inactive."))
        except Exception as e:
            items.append(CheckItem("seed.meta", "WARN", "SeedMeta check unavailable.", {"error": str(e)}))

        errors = [it for it in items if it.status == "ERROR"]
        warns = [it for it in items if it.status == "WARN"]

        summary = {"ok": len([it for it in items if it.status == "OK"]), "warn": len(warns), "error": len(errors), "debug": bool(settings.DEBUG)}

        if as_json:
            payload = {"summary": summary, "items": [{"key": it.key, "status": it.status, "message": it.message, "meta": it.meta or {}} for it in items]}
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING("ops_check results"))
            self.stdout.write(f"- OK: {summary['ok']}  WARN: {summary['warn']}  ERROR: {summary['error']}")
            for it in items:
                style = self.style.SUCCESS if it.status == "OK" else (self.style.WARNING if it.status == "WARN" else self.style.ERROR)
                self.stdout.write(style(f"[{it.status}] {it.key}: {it.message}"))
                if it.meta:
                    self.stdout.write("  " + json.dumps(it.meta, ensure_ascii=False))

        if strict and errors:
            raise SystemExit(2)
