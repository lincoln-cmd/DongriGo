from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from apps.blog.models import Country, Post, Tag


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

    def handle(self, *args, **options):
        verbose: bool = bool(options.get("verbose"))

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

        # missing slug
        missing_country_slug = Country.objects.filter(Q(slug__isnull=True) | Q(slug="")).count()
        if missing_country_slug:
            issues.append(f"Country.slug missing: {missing_country_slug}")
            if verbose:
                info.append(f"  ! missing slug rows: {missing_country_slug}")
        else:
            info.append("- slug missing: OK")

        # iso lengths (optional fields)
        bad_iso_a2 = Country.objects.exclude(iso_a2__isnull=True).exclude(iso_a2="").exclude(
            iso_a2__regex=r"^[A-Za-z]{2}$"
        )
        bad_iso_a3 = Country.objects.exclude(iso_a3__isnull=True).exclude(iso_a3="").exclude(
            iso_a3__regex=r"^[A-Za-z]{3}$"
        )
        if bad_iso_a2.exists():
            issues.append(f"Country.iso_a2 invalid: {bad_iso_a2.count()}")
            if verbose:
                for c in bad_iso_a2[:50]:
                    info.append(f"  ! {c.id} slug={c.slug} iso_a2='{getattr(c,'iso_a2',None)}'")
        else:
            info.append("- iso_a2 format: OK")

        if bad_iso_a3.exists():
            issues.append(f"Country.iso_a3 invalid: {bad_iso_a3.count()}")
            if verbose:
                for c in bad_iso_a3[:50]:
                    info.append(f"  ! {c.id} slug={c.slug} iso_a3='{getattr(c,'iso_a3',None)}'")
        else:
            info.append("- iso_a3 format: OK")

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

        # Duplicate slug within (country, category)
        dup_post_slugs = (
            Post.objects.values("country_id", "category", "slug")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
            .order_by("-c")
        )
        if dup_post_slugs.exists():
            issues.append(f"Post slug duplicates (country+category scope): {dup_post_slugs.count()}")
            if verbose:
                # show up to 50 groups
                for row in dup_post_slugs[:50]:
                    info.append(
                        f"  ! dup country_id={row['country_id']} category={row['category']} slug='{row['slug']}' count={row['c']}"
                    )
        else:
            info.append("- slug duplicates (country+category): OK")

        # Published posts missing published_at (if you use it)
        missing_published_at = Post.objects.filter(is_published=True, published_at__isnull=True).count()
        if missing_published_at:
            issues.append(f"Published posts missing published_at: {missing_published_at}")
            if verbose:
                info.append(f"  ! published_at null rows: {missing_published_at}")
        else:
            info.append("- published_at for published posts: OK")

        # Tag relation sanity (published posts with tags count)
        pub_posts_with_tags = Post.objects.filter(is_published=True, tags__isnull=False).distinct().count()
        info.append(f"- published posts with ≥1 tag: {pub_posts_with_tags}")

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

        # Exit status
        if issues:
            self.stderr.write(self.style.ERROR("Audit finished with issues."))
            # non-zero exit for CI/ops
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("Audit finished with no issues."))
        return
