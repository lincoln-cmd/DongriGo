from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify


@dataclass
class Change:
    model: str
    pk: int
    field: str
    before: Any
    after: Any


def _unique_slug(model_cls, base: str, *, instance_pk=None, max_len: int) -> str:
    base = (base or "").strip()
    s = slugify(base)
    if not s:
        s = slugify(base, allow_unicode=True)
    s = (s or "item")[:max_len]

    candidate = s
    n = 2
    while True:
        qs = model_cls.objects.filter(slug=candidate)
        if instance_pk is not None:
            qs = qs.exclude(pk=instance_pk)
        if not qs.exists():
            return candidate

        suffix = f"-{n}"
        cut = max_len - len(suffix)
        candidate = (s[:cut] if cut > 0 else s) + suffix
        n += 1


def _norm_iso(value: str | None) -> str | None:
    v = (value or "").strip().upper()
    return v or None


def _norm_aliases(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split(",")]
    parts = [p for p in parts if p]
    return ", ".join(parts)


class Command(BaseCommand):
    help = "Check (and optionally fix) data integrity for DongriGo blog app."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Apply conservative fixes (normalize whitespace/case, fill missing slugs, convert '' to NULL).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print report as JSON (safe to store as artifact).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Max number of sample rows per category in the report.",
        )

    def handle(self, *args, **opts):
        fix = bool(opts["fix"])
        as_json = bool(opts["json"])
        limit = int(opts["limit"])

        from apps.blog.models import Country, Post, PostImage  # lazy import

        changes: list[Change] = []
        warnings: list[dict[str, Any]] = []

        # -----------------
        # Countries
        # -----------------
        country_total = Country.objects.count()
        country_fixed = 0

        for c in Country.objects.all().order_by("id"):
            update_fields: list[str] = []

            # ISO normalization ('' -> NULL, strip, upper)
            iso_a2_new = _norm_iso(c.iso_a2)
            iso_a3_new = _norm_iso(c.iso_a3)

            if iso_a2_new != c.iso_a2:
                changes.append(Change("Country", c.pk, "iso_a2", c.iso_a2, iso_a2_new))
                if fix:
                    c.iso_a2 = iso_a2_new
                    update_fields.append("iso_a2")

            if iso_a3_new != c.iso_a3:
                changes.append(Change("Country", c.pk, "iso_a3", c.iso_a3, iso_a3_new))
                if fix:
                    c.iso_a3 = iso_a3_new
                    update_fields.append("iso_a3")

            # Conservative validity checks (do not guess corrections)
            if c.iso_a2 and len(c.iso_a2) != 2:
                warnings.append({"model": "Country", "id": c.pk, "issue": "iso_a2_len", "value": c.iso_a2})
                if fix:
                    changes.append(Change("Country", c.pk, "iso_a2", c.iso_a2, None))
                    c.iso_a2 = None
                    update_fields.append("iso_a2")

            if c.iso_a3 and len(c.iso_a3) != 3:
                warnings.append({"model": "Country", "id": c.pk, "issue": "iso_a3_len", "value": c.iso_a3})
                if fix:
                    changes.append(Change("Country", c.pk, "iso_a3", c.iso_a3, None))
                    c.iso_a3 = None
                    update_fields.append("iso_a3")

            # slug fill (unique)
            if not (c.slug or "").strip():
                warnings.append({"model": "Country", "id": c.pk, "issue": "missing_slug"})
                if fix:
                    base = (c.name_en or c.name or "country").strip()
                    new_slug = _unique_slug(Country, base, instance_pk=c.pk, max_len=50)
                    changes.append(Change("Country", c.pk, "slug", c.slug, new_slug))
                    c.slug = new_slug
                    update_fields.append("slug")

            # aliases normalization
            aliases_new = _norm_aliases(c.aliases)
            if aliases_new != (c.aliases or ""):
                changes.append(Change("Country", c.pk, "aliases", c.aliases, aliases_new))
                if fix:
                    c.aliases = aliases_new
                    update_fields.append("aliases")

            # trim name fields
            name_ko_new = (c.name_ko or "").strip()
            name_en_new = (c.name_en or "").strip()
            if name_ko_new != (c.name_ko or ""):
                changes.append(Change("Country", c.pk, "name_ko", c.name_ko, name_ko_new))
                if fix:
                    c.name_ko = name_ko_new
                    update_fields.append("name_ko")
            if name_en_new != (c.name_en or ""):
                changes.append(Change("Country", c.pk, "name_en", c.name_en, name_en_new))
                if fix:
                    c.name_en = name_en_new
                    update_fields.append("name_en")

            if fix and update_fields:
                c.save(update_fields=list(set(update_fields)))
                country_fixed += 1

        # -----------------
        # Posts
        # -----------------
        post_total = Post.objects.count()
        post_fixed = 0
        missing_image_tokens: list[dict[str, Any]] = []

        for p in Post.objects.select_related("country").prefetch_related("images").all().order_by("id"):
            update_fields: list[str] = []

            if not (p.slug or "").strip():
                warnings.append({"model": "Post", "id": p.pk, "issue": "missing_slug"})
                if fix:
                    new_slug = _unique_slug(Post, p.title or "post", instance_pk=p.pk, max_len=220)
                    changes.append(Change("Post", p.pk, "slug", p.slug, new_slug))
                    p.slug = new_slug
                    update_fields.append("slug")

            if p.is_published and not p.published_at:
                warnings.append({"model": "Post", "id": p.pk, "issue": "missing_published_at"})
                if fix:
                    new_date = timezone.localdate()
                    changes.append(Change("Post", p.pk, "published_at", p.published_at, new_date))
                    p.published_at = new_date
                    update_fields.append("published_at")

            # Token ↔ 이미지 연결 체크(자동 수정은 하지 않음)
            used = p.used_image_ids()
            attached = set(p.images.values_list("id", flat=True))
            missing = sorted(list(used - attached))
            if missing:
                missing_image_tokens.append({
                    "post_id": p.pk,
                    "post_slug": p.slug,
                    "country": getattr(p.country, "slug", None),
                    "missing_image_ids": missing,
                })

            if fix and update_fields:
                p.save(update_fields=list(set(update_fields)))
                post_fixed += 1

        orphan_images = PostImage.objects.filter(post__isnull=True).count()

        report = {
            "fix_applied": fix,
            "summary": {
                "countries_total": country_total,
                "countries_touched": country_fixed,
                "posts_total": post_total,
                "posts_touched": post_fixed,
                "orphan_images": orphan_images,
            },
            "warnings_sample": warnings[:limit],
            "missing_image_tokens_sample": missing_image_tokens[:limit],
            "changes_sample": [
                {"model": ch.model, "id": ch.pk, "field": ch.field, "before": ch.before, "after": ch.after}
                for ch in changes[:limit]
            ],
            "counts": {
                "warnings": len(warnings),
                "missing_image_tokens": len(missing_image_tokens),
                "changes": len(changes),
            },
        }

        if as_json:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return

        self.stdout.write(self.style.SUCCESS("Integrity check finished."))
        self.stdout.write(f"- Countries: {country_total} total, {country_fixed} touched")
        self.stdout.write(f"- Posts: {post_total} total, {post_fixed} touched")
        self.stdout.write(f"- Warnings: {len(warnings)}")
        self.stdout.write(f"- Missing image tokens: {len(missing_image_tokens)}")
        self.stdout.write(f"- Changes: {len(changes)}")

        if warnings:
            self.stdout.write(self.style.WARNING("Sample warnings:"))
            for w in warnings[:min(limit, 10)]:
                self.stdout.write(f"  - {w}")

        if missing_image_tokens:
            self.stdout.write(self.style.WARNING("Sample missing image tokens:"))
            for row in missing_image_tokens[:min(limit, 10)]:
                self.stdout.write(f"  - {row}")
