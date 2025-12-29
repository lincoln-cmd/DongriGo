import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def highlight(text, query):
    """
    Safe highlight: escape original text, then wrap matched parts with <mark>.
    - Case-insensitive
    - Multiple words supported (split by whitespace)
    """
    if not text:
        return ""
    if not query:
        return escape(text)

    raw = str(text)
    q = str(query).strip()
    if not q:
        return escape(raw)

    # tokenize query (space-separated)
    tokens = [t for t in re.split(r"\s+", q) if t]
    if not tokens:
        return escape(raw)

    # escape first to prevent XSS
    escaped = escape(raw)

    # build regex for any token, longest first to reduce nested overlaps
    tokens_sorted = sorted(set(tokens), key=len, reverse=True)
    pattern = re.compile("(" + "|".join(re.escape(t) for t in tokens_sorted) + ")", re.IGNORECASE)

    highlighted = pattern.sub(r"<mark>\1</mark>", escaped)
    return mark_safe(highlighted)
