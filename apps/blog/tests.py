from django.core.management import call_command
from django.test import TestCase
from django.utils.encoding import iri_to_uri

from apps.blog.models import Country, Tag, Post, PostSlugHistory, TagSlugHistory


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

        PostSlugHistory.objects.create(post=p, country=c, category=Post.Category.TRAVEL, old_slug="ᄉ")

        with self.assertRaises(SystemExit):
            call_command("fix_slug_history")

        call_command("fix_slug_history", "--apply")
        self.assertEqual(PostSlugHistory.objects.count(), 0)

    def test_fix_slug_history_detects_collision_with_current_post_slug(self):
        c = Country.objects.create(name="Korea", slug="korea", iso_a2="KR", iso_a3="KOR")
        p1 = Post.objects.create(country=c, category=Post.Category.TRAVEL, title="A", slug="alpha")
        p2 = Post.objects.create(country=c, category=Post.Category.TRAVEL, title="B", slug="beta")

        PostSlugHistory.objects.create(post=p2, country=c, category=Post.Category.TRAVEL, old_slug="alpha")

        with self.assertRaises(SystemExit):
            call_command("fix_slug_history")

        call_command("fix_slug_history", "--apply")
        self.assertEqual(PostSlugHistory.objects.count(), 0)


class TagSlugHistoryRedirectTests(TestCase):
    def test_unicode_tag_slug_resolves_200(self):
        tag = Tag.objects.create(name="온천")  # slug 자동: '온천'
        # ✅ CI의 ManifestStaticFilesStorage(collectstatic 미실행) 환경에서 home.html 렌더 시 favicon manifest 에러가 날 수 있음.
        # ✅ 따라서 기능 검증 목적(라우팅/응답 OK)에 맞춰 HTMX로 보드 partial만 렌더링한다.
        resp = self.client.get(
            f"/tags/{tag.slug}/",
            secure=True,
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse("HX-Redirect" in resp.headers)

    def test_old_tag_slug_redirects_to_canonical_and_keeps_query(self):
        tag = Tag.objects.create(name="온천", slug="spa")
        tag.slug = "온천"
        tag.save()

        self.assertEqual(TagSlugHistory.objects.count(), 1)
        self.assertTrue(TagSlugHistory.objects.filter(old_slug="spa").exists())

        resp = self.client.get("/tags/spa/?page=2&q=x&sort=old", secure=True)
        self.assertEqual(resp.status_code, 301)

        expected = iri_to_uri("/tags/온천/?page=2&q=x&sort=old")
        self.assertEqual(resp["Location"], expected)

    def test_old_tag_slug_htmx_returns_204_with_hx_redirect(self):
        tag = Tag.objects.create(name="온천", slug="spa")
        tag.slug = "온천"
        tag.save()

        resp = self.client.get(
            "/tags/spa/?q=x",
            HTTP_HX_REQUEST="true",
            secure=True,
        )
        self.assertEqual(resp.status_code, 204)

        expected = iri_to_uri("/tags/온천/?q=x")
        self.assertEqual(resp["HX-Redirect"], expected)
