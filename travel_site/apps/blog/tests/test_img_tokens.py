from django.test import TestCase
from apps.blog.views import replace_img_tokens_preserving_code

class ImgTokenReplaceTests(TestCase):
    def test_does_not_replace_in_fenced_code(self):
        md = "before\n```python\n[[img:123]]\n```\nafter"
        html, used = replace_img_tokens_preserving_code(md, images_by_id={})
        self.assertIn("[[img:123]]", html)
        self.assertEqual(len(used), 0)

    def test_does_not_replace_in_inline_code(self):
        md = "before `[[img:123]]` after"
        html, used = replace_img_tokens_preserving_code(md, images_by_id={})
        self.assertIn("`[[img:123]]`", html)
        self.assertEqual(len(used), 0)
