from django import template
from django.utils.safestring import mark_safe
import markdown as md
import bleach

register = template.Library()

# ✅ 허용할 태그(보수적으로 시작)
ALLOWED_TAGS = [
    "p", "br",
    "h1", "h2", "h3", "h4",
    "strong", "em", "blockquote",
    "ul", "ol", "li",
    "hr",
    "pre", "code",
    "table", "thead", "tbody", "tr", "th", "td",
    "a",
    "img",
]

# ✅ 허용할 속성
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel", "target"],
    "img": ["src", "alt", "title", "width", "height", "loading"],
    "code": ["class"],
    "pre": ["class"],
    "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
}

# ✅ 허용할 URL 스킴(보수적으로)
ALLOWED_PROTOCOLS = ["http", "https"]

@register.filter
def render_markdown(text: str) -> str:
    if not text:
        return ""

    raw_html = md.markdown(
        text,
        extensions=[
            "fenced_code",   # ``` code
            "codehilite",    # pygments class
            "tables",        # tables
        ],
        extension_configs={
            "codehilite": {"guess_lang": False, "noclasses": False}
        },
    )

    clean_html = bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )

    # ✅ 링크에 rel/target 보강(선택)
    clean_html = bleach.linkify(clean_html, callbacks=[
        bleach.callbacks.nofollow,
        bleach.callbacks.target_blank,
    ])

    return mark_safe(clean_html)
