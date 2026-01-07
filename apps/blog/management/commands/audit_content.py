from __future__ import annotations

import re
from typing import Iterable

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.utils.text import slugify

from apps.blog.models import Country, Post, PostSlugHistory, Tag


ISO_A2_RE = re.compile(r"^[A-Z]{2}$")
ISO_A3_RE = re.compile(r"^[A-Z]{3}$")


def _smart_slugify(base: str) -> str:
    """Slugify helper mirroring our model behavior (fallback allow_unicode)."""
    base = (base or "").strip()
    s = slugify(base)
    if not s:
        s = slugify(base, allow_unicode=True)
    return s or ""


def _print_lines(lines: Iterable[str]) -> None:
    for line in lines:
        print(line)


class Command(BaseCommand):
    help = "Read-only audit for content data integrity (Country/Tag/Post). Does NOT modify DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print more details for each issue category.",
        )
        parser.add_argument(
            "--sample",
            type=int,
            default=50,
            help="Max sample rows to print per issue group when --verbose is set (default 50).",
        )

    def handle(self, *args, **options):
        verbose: bool = bool(options.get("verbose"))
        sample: int = int(options.get("sample") or 50)

        issues: list[str] = []
        info: list[str] = []

        info.append("=== DongriGo Content Audit (read-only) ===")

        # -------------------------
        # Country checks
        # -------------------------
        info.append("\n[Country]")
        country_count = Country.objects.count()
        info.append(f"- total: {country_count}")

        # slug duplicates
        dup_country_slugs = (
            Country.objects.values("slug")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
            .order_by("-c")
        )
        if dup_country_slugs.exists():
            issues.append(f"Country.slug duplicate groups: {dup_country_slugs.count()}")
            if verbose:
                for row in dup_country_slugs:
                    info.append(f"  ! dup slug='{row['slug']}' count={row['c']}")
        else:
            info.append("- slug duplicates: OK")

        # slug casing
        non_lower_country_slugs = Country.objects.exclude(slug=Lower("slug")).count()
        if non_lower_country_slugs:
            issues.append(f"Country.slug not lowercase: {non_lower_country_slugs}")
            if verbose:
                for c in Country.objects.exclude(slug=Lower("slug")).only("id", "slug")[:sample]:
                    info.append(f"  ! {c.id} slug='{c.slug}'")
        else:
            info.append("- slug lowercase: OK")

        # missing slug
        missing_country_slug = Country.objects.filter(Q(slug__isnull=True) | Q(slug="")).count()
        if missing_country_slug:
            issues.append(f"Country.slug missing: {missing_country_slug}")
            if verbose:
                info.append(f"  ! missing slug rows: {missing_country_slug}")
        else:
            info.append("- slug missing: OK")

        # ISO format (optional fields) - should be uppercase 2/3 letters
        bad_iso_a2_ids: list[tuple[int, str, str]] = []
        bad_iso_a3_ids: list[tuple[int, str, str]] = []
        for c in Country.objects.all().only("id", "slug", "iso_a2", "iso_a3").iterator():
            a2 = (c.iso_a2 or "").strip()
            a3 = (c.iso_a3 or "").strip()
            if a2 and not ISO_A2_RE.match(a2):
                bad_iso_a2_ids.append((c.id, c.slug, a2))
            if a3 and not ISO_A3_RE.match(a3):
                bad_iso_a3_ids.append((c.id, c.slug, a3))

        if bad_iso_a2_ids:
            issues.append(f"Country.iso_a2 invalid: {len(bad_iso_a2_ids)}")
            if verbose:
                for cid, slug, a2 in bad_iso_a2_ids[:sample]:
                    info.append(f"  ! {cid} slug={slug} iso_a2='{a2}'")
        else:
            info.append("- iso_a2 format: OK")

        if bad_iso_a3_ids:
            issues.append(f"Country.iso_a3 invalid: {len(bad_iso_a3_ids)}")
            if verbose:
                for cid, slug, a3 in bad_iso_a3_ids[:sample]:
                    info.append(f"  ! {cid} slug={slug} iso_a3='{a3}'")
        else:
            info.append("- iso_a3 format: OK")

        # iso_a3 duplicates (DB unique should prevent, but keep as a guard)
        dup_iso_a3 = (
            Country.objects.exclude(iso_a3__isnull=True)
            .exclude(iso_a3="")
            .values("iso_a3")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
            .order_by("-c")
        )
        if dup_iso_a3.exists():
            issues.append(f"Country.iso_a3 duplicate groups: {dup_iso_a3.count()}")
            if verbose:
                for row in dup_iso_a3[:sample]:
                    info.append(f"  ! dup iso_a3='{row['iso_a3']}' count={row['c']}")
        else:
            info.append("- iso_a3 duplicates: OK")

        # -------------------------
        # Tag checks
        # -------------------------
        info.append("\n[Tag]")
        tag_count = Tag.objects.count()
        info.append(f"- total: {tag_count}")

        dup_tag_slugs = (
            Tag.objects.values("slug")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
            .order_by("-c")
        )
        if dup_tag_slugs.exists():
            issues.append(f"Tag.slug duplicate groups: {dup_tag_slugs.count()}")
            if verbose:
                for row in dup_tag_slugs:
                    info.append(f"  ! dup slug='{row['slug']}' count={row['c']}")
        else:
            info.append("- slug duplicates: OK")

        missing_tag_slug = Tag.objects.filter(Q(slug__isnull=True) | Q(slug="")).count()
        if missing_tag_slug:
            issues.append(f"Tag.slug missing: {missing_tag_slug}")
            if verbose:
                info.append(f"  ! missing slug rows: {missing_tag_slug}")
        else:
            info.append("- slug missing: OK")

        missing_tag_name = Tag.objects.filter(Q(name__isnull=True) | Q(name="")).count()
        if missing_tag_name:
            issues.append(f"Tag.name missing: {missing_tag_name}")
            if verbose:
                info.append(f"  ! missing name rows: {missing_tag_name}")
        else:
            info.append("- name missing: OK")

        # name case-insensitive collisions (DB unique is case-sensitive on most DBs)
        dup_tag_name_ci = (
            Tag.objects.annotate(name_l=Lower("name"))
            .values("name_l")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
            .order_by("-c")
        )
        if dup_tag_name_ci.exists():
            issues.append(f"Tag.name case-insensitive duplicate groups: {dup_tag_name_ci.count()}")
            if verbose:
                for row in dup_tag_name_ci[:sample]:
                    info.append(f"  ! dup (ci) name='{row['name_l']}' count={row['c']}")
        else:
            info.append("- name case-insensitive duplicates: OK")

        # slug should be slugified from name (or slugified-2, -3 ...)
        tag_slug_mismatch = []
        for t in Tag.objects.all().only("id", "name", "slug").iterator():
            expected = _smart_slugify(t.name)[:60]
            if not expected:
                continue
            if not (t.slug == expected or t.slug.startswith(expected + "-")):
                tag_slug_mismatch.append((t.id, t.name, t.slug, expected))
        if tag_slug_mismatch:
            issues.append(f"Tag.slug unexpected for name: {len(tag_slug_mismatch)}")
            if verbose:
                for tid, name, slug, expected in tag_slug_mismatch[:sample]:
                    info.append(f"  ! {tid} name='{name}' slug='{slug}' expected~='{expected}'")
        else:
            info.append("- slug aligns with name: OK")

        # orphan tags (no posts)
        orphan_tags = Tag.objects.annotate(pc=Count("posts")).filter(pc=0).count()
        info.append(f"- orphan tags (0 posts): {orphan_tags}")

        # -------------------------
        # Post checks
        # -------------------------
        info.append("\n[Post]")
        post_total = Post.objects.count()
        post_pub = Post.objects.filter(is_published=True).count()
        info.append(f"- total: {post_total} (published: {post_pub})")

        missing_post_slug = Post.objects.filter(Q(slug__isnull=True) | Q(slug="")).count()
        if missing_post_slug:
            issues.append(f"Post.slug missing: {missing_post_slug}")
            if verbose:
                info.append(f"  ! missing slug rows: {missing_post_slug}")
        else:
            info.append("- slug missing: OK")

        non_lower_post_slugs = Post.objects.exclude(slug=Lower("slug")).count()
        if non_lower_post_slugs:
            issues.append(f"Post.slug not lowercase: {non_lower_post_slugs}")
            if verbose:
                for p in Post.objects.exclude(slug=Lower("slug")).only("id", "slug")[:sample]:
                    info.append(f"  ! {p.id} slug='{p.slug}'")
        else:
            info.append("- slug lowercase: OK")

        # Duplicate slug within (country, category) (even though Post.slug is globally unique)
        dup_post_slugs_scoped = (
            Post.objects.values("country_id", "category", "slug")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
            .order_by("-c")
        )
        if dup_post_slugs_scoped.exists():
            issues.append(
                f"Post slug duplicates (country+category scope): {dup_post_slugs_scoped.count()}"
            )
            if verbose:
                for row in dup_post_slugs_scoped[:sample]:
                    info.append(
                        f"  ! dup country_id={row['country_id']} category={row['category']} slug='{row['slug']}' count={row['c']}"
                    )
        else:
            info.append("- slug duplicates (country+category): OK")

        # Published posts missing published_at
        missing_published_at = Post.objects.filter(is_published=True, published_at__isnull=True).count()
        if missing_published_at:
            issues.append(f"Published posts missing published_at: {missing_published_at}")
            if verbose:
                info.append(f"  ! published_at null rows: {missing_published_at}")
        else:
            info.append("- published_at for published posts: OK")

        # Tag relation sanity
        pub_posts_with_tags = Post.objects.filter(is_published=True, tags__isnull=False).distinct().count()
        info.append(f"- published posts with ≥1 tag: {pub_posts_with_tags}")

        # -------------------------
        # PostSlugHistory checks
        # -------------------------
        info.append("\n[PostSlugHistory]")
        hist_total = PostSlugHistory.objects.count()
        info.append(f"- total: {hist_total}")

        # old_slug must not collide with any *other* current post slug in same (country, category)
        collisions = []
        for h in PostSlugHistory.objects.select_related("post", "country").only(
            "id",
            "country_id",
            "category",
            "old_slug",
            "post_id",
            "post__slug",
        ).iterator():
            if not h.old_slug:
                continue

            exists_other = Post.objects.filter(
                country_id=h.country_id,
                category=h.category,
                slug=h.old_slug,
            ).exclude(id=h.post_id).exists()
            if exists_other:
                collisions.append((h.id, h.country_id, h.category, h.old_slug, h.post_id))

            if getattr(h.post, "slug", None) == h.old_slug:
                collisions.append((h.id, h.country_id, h.category, h.old_slug, h.post_id))

        if collisions:
            issues.append(f"PostSlugHistory collisions/stale rows: {len(collisions)}")
            if verbose:
                for hid, cid, cat, old_slug, post_id in collisions[:sample]:
                    info.append(
                        f"  ! hist_id={hid} country_id={cid} category={cat} old_slug='{old_slug}' post_id={post_id}"
                    )
        else:
            info.append("- collisions with current slugs: OK")

        # -------------------------
        # Output summary
        # -------------------------
        info.append("\n[Summary]")
        if issues:
            info.append(f"- issues: {len(issues)}")
            for it in issues:
                info.append(f"  - {it}")
        else:
            info.append("- issues: 0 ✅")

        _print_lines(info)

        if issues:
            self.stderr.write(self.style.ERROR("Audit finished with issues."))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("Audit finished with no issues."))
        return
