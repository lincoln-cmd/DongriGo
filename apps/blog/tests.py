from django.core.management import call_command
from django.test import TestCase

from apps.blog.models import Country, Tag, Post, PostSlugHistory


class AuditContentCommandTests(TestCase):
    def test_audit_content_no_issues_exits_zero(self):
        Country.objects.create(name="Korea", slug="korea", iso_a2="KR", iso_a3="KOR")
        Tag.objects.create(name="Test Tag", slug="test-tag")
        call_command("audit_content")

    def test_audit_content_detects_invalid_iso_and_empty_tag_name(self):
        Country.objects.create(name="BadISO", slug="badiso", iso_a2="k1", iso_a3="ko1")
        Tag.objects.create(name="", slug="empty")

        with self.assertRaises(SystemExit) as ctx:
            call_command("audit_content")
        self.assertNotEqual(ctx.exception.code, 0)


class FixSlugHistoryCommandTests(TestCase):
    def test_fix_slug_history_detects_invalid_old_slug_and_can_apply(self):
        c = Country.objects.create(name="Korea", slug="korea", iso_a2="KR", iso_a3="KOR")
        p = Post.objects.create(country=c, category=Post.Category.TRAVEL, title="T1", slug="t1")

        # invalid slug (unicode jamo) - model save does not validate automatically
        PostSlugHistory.objects.create(post=p, country=c, category=Post.Category.TRAVEL, old_slug="ᄉ")

        # dry-run should exit non-zero
        with self.assertRaises(SystemExit):
            call_command("fix_slug_history")

        # apply should delete the row
        call_command("fix_slug_history", "--apply")
        self.assertEqual(PostSlugHistory.objects.count(), 0)

    def test_fix_slug_history_detects_collision_with_current_post_slug(self):
        c = Country.objects.create(name="Korea", slug="korea", iso_a2="KR", iso_a3="KOR")
        p1 = Post.objects.create(country=c, category=Post.Category.TRAVEL, title="A", slug="alpha")
        p2 = Post.objects.create(country=c, category=Post.Category.TRAVEL, title="B", slug="beta")

        # old_slug collides with p1's current slug in same (country, category)
        PostSlugHistory.objects.create(post=p2, country=c, category=Post.Category.TRAVEL, old_slug="alpha")

        with self.assertRaises(SystemExit):
            call_command("fix_slug_history")

        call_command("fix_slug_history", "--apply")
        self.assertEqual(PostSlugHistory.objects.count(), 0)

from django.urls import reverse

from apps.blog.models import Tag, TagSlugAlias

class TagAliasRedirectTests(TestCase):
    def test_tag_detail_redirects_from_alias(self):
        t = Tag.objects.create(name="온천", slug="온천")
        TagSlugAlias.objects.create(tag=t, old_slug="spa")

        url = reverse("blog:tag_detail", kwargs={"tag_slug": "spa"})
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (301, 302))

        target = reverse("blog:tag_detail", kwargs={"tag_slug": "온천"})
        self.assertTrue(resp["Location"].endswith(target))
