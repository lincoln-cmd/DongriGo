from django.core.management import call_command
from django.test import TestCase

from apps.blog.models import Country, Tag


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
