# apps/blog/views.py
from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import Country, Post, PostImage

try:
    from cloudinary import CloudinaryImage
except Exception:
    CloudinaryImage = None


# ---------------------------
# Category helpers
# ---------------------------

CATEGORY_MAP = {
    "history": "HISTORY",
    "culture": "CULTURE",
    "travel": "TRAVEL",
    "my-log": "MY_LOG",
}
REVERSE_CATEGORY_MAP = {v: k for k, v in CATEGORY_MAP.items()}  # HISTORY -> history


def normalize_category(value: str | None) -> str | None:
    if not value:
        return None
    return CATEGORY_MAP.get(value, value)


def category_to_slug(value: str | None) -> str | None:
    if not value:
        return None
    return REVERSE_CATEGORY_MAP.get(value, value.lower())


# ---------------------------
# Markdown + [[img:id]] replacement (preserve code)
# ---------------------------

IMG_TOKEN_RE = re.compile(r"\[\[img:(\d+)(?:\|([^\]]+))?\]\]")

FENCED_RE = re.compile(
    r"(^```.*?$.*?^```[ \t]*$|^~~~.*?$.*?^~~~[ \t]*$)",
    re.MULTILINE | re.DOTALL,
)
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1", re.DOTALL)


def _parse_img_opts(opt_str: str) -> dict:
    """
    opt_str 예: 'w=480|h=320|crop=fill|caption="hello world"'
    """
    opts = {}
    if not opt_str:
        return opts

    for part in opt_str.split("|"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip().lower()
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            opts[k] = v
        else:
            opts[part.lower()] = "1"
    return opts


def _cloudinary_transformed_url(image_field, w=None, h=None, crop=None) -> str:
    if not image_field:
        return ""
    fallback = getattr(image_field, "url", "")

    public_id = getattr(image_field, "public_id", None)
    if not public_id or CloudinaryImage is None:
        return fallback

    t = ["q_auto", "f_auto"]
    if w:
        t.append(f"w_{w}")
    if h:
        t.append(f"h_{h}")
    if crop:
        t.append(f"c_{crop}")
    else:
        t.append("c_limit")

    try:
        return CloudinaryImage(public_id).build_url(transformation=",".join(t))
    except Exception:
        return fallback


def _render_img_html(img_obj: PostImage, opts: dict) -> str:
    w = opts.get("w")
    h = opts.get("h")
    crop = opts.get("crop")

    w_int = int(w) if (w and w.isdigit()) else None
    h_int = int(h) if (h and h.isdigit()) else None

    caption = opts.get("caption")
    if caption is None:
        caption = img_obj.caption or ""

    alt = opts.get("alt")
    if alt is None:
        alt = caption or ""

    show_caption = bool(caption)

    src = _cloudinary_transformed_url(img_obj.image, w=w_int, h=h_int, crop=crop)

    esc_alt = escape(alt)
    esc_cap = escape(caption)

    html = [
        '<figure class="md-img">',
        f'<img class="md-img__img" src="{src}" alt="{esc_alt}" loading="lazy" />',
    ]
    if show_caption:
        html.append(f'<figcaption class="hint md-img__cap">{esc_cap}</figcaption>')
    html.append("</figure>")
    return "".join(html)



def replace_img_tokens_preserving_code(md_text: str, images_by_id: Dict[int, PostImage]) -> Tuple[str, Set[int]]:
    used_ids: Set[int] = set()

    def _replace_tokens(text: str) -> str:
        def _sub(m: re.Match) -> str:
            img_id = int(m.group(1))
            opt_str = m.group(2) or ""
            img = images_by_id.get(img_id)
            if not img:
                return m.group(0)
            opts = _parse_img_opts(opt_str)
            used_ids.add(img_id)
            return _render_img_html(img, opts)

        return IMG_TOKEN_RE.sub(_sub, text)

    def replace_in_plain_text(plain: str) -> str:
        # inline code(`...`) 구간 보호
        out: List[str] = []
        last = 0
        for m in INLINE_CODE_RE.finditer(plain):
            out.append(_replace_tokens(plain[last:m.start()]))
            out.append(m.group(0))  # inline code는 그대로
            last = m.end()
        out.append(_replace_tokens(plain[last:]))
        return "".join(out)

    # fenced code block 보호
    result: List[str] = []
    last = 0
    for m in FENCED_RE.finditer(md_text or ""):
        result.append(replace_in_plain_text((md_text or "")[last:m.start()]))
        result.append(m.group(0))  # fenced code block은 그대로
        last = m.end()
    result.append(replace_in_plain_text((md_text or "")[last:]))

    return "".join(result), used_ids


def render_markdown(md_text: str) -> str:
    """
    Markdown -> HTML (python-markdown)
    """
    md_text = md_text or ""
    try:
        import markdown as md
    except Exception:
        # markdown 패키지 없으면 안전하게 escape 처리
        return mark_safe("<p>" + escape(md_text).replace("\n", "<br>") + "</p>")

    html = md.markdown(
        md_text,
        extensions=["fenced_code", "codehilite", "tables", "nl2br"],
        extension_configs={
            "codehilite": {"guess_lang": False, "noclasses": False}
        },
        output_format="html5",
    )
    return html


# ---------------------------
# View
# ---------------------------

def home(request, country_slug=None, category_slug=None, post_slug=None):
    countries = Country.objects.all()

    country = country_slug or request.GET.get("country")
    category_raw = category_slug or request.GET.get("category")
    post = post_slug or request.GET.get("post")

    selected_country = None
    selected_post = None
    posts = Post.objects.none()
    page_obj = None
    q = (request.GET.get("q") or "").strip()

    category = normalize_category(category_raw)

    selected_post_html = None
    gallery_images = []

    if country:
        selected_country = get_object_or_404(Country, slug=country)

        valid_categories = set(Post.Category.values)
        if not category or category not in valid_categories:
            category = Post.Category.HISTORY

        qs = Post.objects.filter(
            country=selected_country,
            is_published=True,
            category=category,
        )

        if q:
            qs = qs.filter(title__icontains=q)

        if post:
            # 이미지 미리 가져오면 아래에서 추가 쿼리 줄어듦
            selected_post = get_object_or_404(
                Post.objects.prefetch_related("images"),
                slug=post,
                is_published=True,
                country=selected_country,
                category=category,
            )

        page_size = 10
        page_param = request.GET.get("page")
        page_number = page_param or 1

        if selected_post and not page_param:
            ids = list(qs.values_list("id", flat=True))
            try:
                idx = ids.index(selected_post.id)
                page_number = (idx // page_size) + 1
            except ValueError:
                page_number = 1

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page_number)
        posts = page_obj.object_list

        if selected_post:
            imgs = list(selected_post.images.all().order_by("order", "id"))
            images_by_id = {img.id: img for img in imgs}

            md_with_imgs, used_ids = replace_img_tokens_preserving_code(selected_post.content or "", images_by_id)
            selected_post_html = render_markdown(md_with_imgs)

            gallery_images = [img for img in imgs if img.id not in used_ids]

    tabs = [(k, l, category_to_slug(k)) for k, l in Post.Category.choices]
    selected_category_slug = category_to_slug(category)

    category_path = (
        f"/{selected_country.slug}/{selected_category_slug}/"
        if selected_country and selected_category_slug
        else "/"
    )

    context = {
        "countries": countries,
        "selected_country": selected_country,
        "selected_category": category,
        "selected_category_slug": selected_category_slug,
        "posts": posts,
        "selected_post": selected_post,
        "categories": Post.Category,
        "tabs": tabs,
        "page_obj": page_obj,
        "category_path": category_path,
        "q": q,
        "selected_post_html": selected_post_html,
        "gallery_images": gallery_images,
    }

    if request.headers.get("HX-Request") == "true":
        return render(request, "blog/_board.html", context)
    return render(request, "blog/home.html", context)
