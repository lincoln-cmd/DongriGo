from __future__ import annotations

import re
from urllib.parse import urlencode

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import FieldError
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import Country, Post, PostImage, PostSlugHistory, Tag


def get_tabs():
    return [
        ("TRAVEL", "Travel", "travel"),
        ("HISTORY", "History", "history"),
        ("CULTURE", "Culture", "culture"),
        ("MY_LOG", "My Log", "my-log"),
    ]


def get_sort_options():
    # ✅ 보수적 최소 정렬(운영 리스크 낮음)
    return [
        ("new", "최신"),
        ("old", "오래된"),
        ("title", "제목"),
    ]


def resolve_selected_category(category_slug: str | None):
    mapping = {
        "travel": Post.Category.TRAVEL,
        "history": Post.Category.HISTORY,
        "culture": Post.Category.CULTURE,
        "my-log": Post.Category.MY_LOG,
    }
    if not category_slug:
        return Post.Category.TRAVEL, "travel"

    cat = mapping.get(category_slug, Post.Category.TRAVEL)
    inv = {v: k for k, v in mapping.items()}
    return cat, inv.get(cat, "travel")


def is_htmx(request) -> bool:
    return (
        request.headers.get("HX-Request") == "true"
        or request.META.get("HTTP_HX_REQUEST") == "true"
    )


def _extract_used_image_ids_from_content(content: str) -> set[int]:
    if not content:
        return set()
    ids: set[int] = set()
    for m in re.finditer(r"\[\[img:(\d+)\]\]", content):
        try:
            ids.add(int(m.group(1)))
        except Exception:
            pass
    return ids


def _base_context_for_home(request):
    """
    home.html(좌: globe + 국가 리스트) 공통 컨텍스트
    """
    countries_qs = Country.objects.all()

    # globe.js로 내려줄 데이터 (필드가 일부 없는 환경도 안전하게)
    try:
        countries_for_globe = list(
            countries_qs.values(
                "name",
                "name_ko",
                "name_en",
                "slug",
                "aliases",
                "iso_a2",
                "iso_a3",
            )
        )
    except FieldError:
        countries_for_globe = list(countries_qs.values("name", "slug"))

    return {
        "countries": countries_qs,
        "countries_for_globe": countries_for_globe,
    }


@staff_member_required
@require_POST
def admin_live_preview(request):
    """
    admin에서 content 작성 중 live preview용 (렌더된 HTML 반환)
    """
    content = (request.POST.get("content") or "").strip()
    if content == "":
        return HttpResponse("", content_type="text/html; charset=utf-8")

    post_id = (request.POST.get("post_id") or "").strip()

    obj = None
    if post_id.isdigit():
        try:
            obj = (
                Post.objects
                .prefetch_related(
                    Prefetch("images", queryset=PostImage.objects.order_by("order", "id"))
                )
                .get(pk=int(post_id))
            )
        except Post.DoesNotExist:
            obj = None

    if obj is None:
        obj = Post(content=content)
    else:
        obj.content = content

    html = obj.rendered_content()
    return HttpResponse(html, content_type="text/html; charset=utf-8")


def home(request, country_slug=None, category_slug=None, post_slug=None, **kwargs):
    """
    메인 화면:
    - 좌: globe.gl
    - 우: HTMX로 #boardContent 부분 갱신
    """

    # URLConf/호출 방식이 섞여도 안전하게 보정
    if country_slug is None:
        country_slug = kwargs.get("country_slug") or kwargs.get("slug") or kwargs.get("country")
    if category_slug is None:
        category_slug = kwargs.get("category_slug") or kwargs.get("cat") or kwargs.get("category")
    if post_slug is None:
        post_slug = kwargs.get("post_slug") or kwargs.get("post") or kwargs.get("postSlug")

    ctx = _base_context_for_home(request)

    selected_country = None
    if country_slug:
        try:
            selected_country = Country.objects.get(slug=country_slug)
        except Country.DoesNotExist:
            selected_country = None

    selected_category, selected_category_slug = resolve_selected_category(category_slug)

    q = (request.GET.get("q") or "").strip()
    is_searching = bool(q)

    # ---------------------------------------------
    # Phase 3B: context-based navigation (Tag → Post detail → Back)
    # ---------------------------------------------
    src = (request.GET.get("src") or "").strip()
    from_tag = (request.GET.get("from_tag") or "").strip()
    from_page_raw = (request.GET.get("from_page") or "").strip()
    from_q = (request.GET.get("from_q") or "").strip()
    from_sort = (request.GET.get("from_sort") or "").strip()

    from_tags = (src == "tags" and bool(from_tag))
    from_page = from_page_raw if from_page_raw.isdigit() else "1"

    tags_back_url = ""
    if from_tags:
        params = {"page": from_page}
        if from_q:
            params["q"] = from_q
        # ✅ 태그 상세 정렬 상태 유지 (new는 기본값이라 생략)
        if from_sort and from_sort != "new":
            params["sort"] = from_sort
        tags_back_url = f"/tags/{from_tag}/?{urlencode(params)}"

    # 국가 보드 정렬
    sort = (request.GET.get("sort") or "new").strip()
    sort_options = get_sort_options()
    sort_keys = {v for v, _ in sort_options}
    if sort not in sort_keys:
        sort = "new"

    # ✅ 국가 보드 내 tag 필터 (?tag=<slug>)
    tag_slug = (request.GET.get("tag") or "").strip()
    selected_tag = None
    tag_not_found = False
    if tag_slug:
        try:
            selected_tag = Tag.objects.get(slug=tag_slug)
        except Tag.DoesNotExist:
            selected_tag = None
            tag_not_found = True

    # 빈 상태 UX용 카운트
    country_posts_total = 0
    if selected_country:
        country_posts_total = Post.objects.filter(
            is_published=True,
            country=selected_country
        ).count()

    base_category_qs = Post.objects.filter(
        is_published=True,
        category=selected_category
    )
    if selected_country:
        base_category_qs = base_category_qs.filter(country=selected_country)

    if selected_tag:
        base_category_qs = base_category_qs.filter(tags=selected_tag)
    elif tag_not_found:
        base_category_qs = base_category_qs.none()

    category_posts_total = base_category_qs.count()

    posts_qs = base_category_qs
    if is_searching:
        posts_qs = posts_qs.filter(Q(title__icontains=q) | Q(content__icontains=q))

    if sort == "old":
        posts_qs = posts_qs.order_by("published_at", "created_at", "id")
    elif sort == "title":
        posts_qs = posts_qs.order_by("title", "-published_at", "-created_at", "-id")
    else:
        posts_qs = posts_qs.order_by("-published_at", "-created_at", "-id")

    paginator = Paginator(posts_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page") or "1")
    posts = page_obj.object_list
    search_results_total = page_obj.paginator.count

    selected_post = None
    selected_post_html = ""
    gallery_images = None

    # 상세
    if post_slug and selected_country:
        try:
            selected_post = (
                Post.objects
                .prefetch_related(
                    Prefetch("images", queryset=PostImage.objects.order_by("order", "id")),
                    "tags",
                )
                .get(
                    country=selected_country,
                    category=selected_category,
                    slug=post_slug,
                    is_published=True,
                )
            )

            selected_post_html = selected_post.rendered_content()

            if hasattr(selected_post, "used_image_ids") and callable(getattr(selected_post, "used_image_ids")):
                used_ids = set(selected_post.used_image_ids())
            else:
                used_ids = _extract_used_image_ids_from_content(selected_post.content)

            gallery_images = (
                selected_post.images
                .exclude(id__in=used_ids)
                .order_by("order", "id")
            )

        except Post.DoesNotExist:
            # 예전 slug면 최신 URL로 301
            h = (
                PostSlugHistory.objects
                .select_related("post", "country")
                .filter(
                    country=selected_country,
                    category=selected_category,
                    old_slug=post_slug,
                    post__is_published=True,
                )
                .order_by("-created_at")
                .first()
            )
            if h and h.post:
                new_url = h.post.get_absolute_url()
                if is_htmx(request):
                    resp = HttpResponse("", status=204)
                    resp["HX-Redirect"] = new_url
                    return resp
                return redirect(new_url, permanent=True)

            selected_post = None

    category_path = f"/{selected_country.slug}/{selected_category_slug}/" if selected_country else "/"

    ctx.update({
        "board_view": "country",

        "selected_country": selected_country,
        "selected_category": selected_category,
        "selected_category_slug": selected_category_slug,
        "tabs": get_tabs(),

        "posts": posts,
        "page_obj": page_obj,
        "selected_post": selected_post,
        "selected_post_html": selected_post_html,
        "gallery_images": gallery_images,

        "q": q,
        "is_searching": is_searching,

        # Tag-origin context (B안)
        "from_tags": from_tags,
        "from_tag": from_tag,
        "from_page": from_page,
        "from_q": from_q,
        "from_sort": from_sort,
        "tags_back_url": tags_back_url,

        # 국가 보드 정렬
        "sort": sort,
        "sort_options": sort_options,

        # 국가 보드 내 tag filter
        "tag": tag_slug,
        "tag_slug": tag_slug,
        "selected_tag": selected_tag,
        "tag_not_found": tag_not_found,

        # 빈 상태 UX
        "country_posts_total": country_posts_total,
        "category_posts_total": category_posts_total,
        "search_results_total": search_results_total,

        "category_path": category_path,
    })

    # globe/search가 잘못된 slug를 보냈을 때 보드 비우지 않게 204
    if is_htmx(request) and country_slug and not selected_country:
        return HttpResponse("", status=204)

    if is_htmx(request):
        return render(request, "blog/_board.html", ctx)

    return render(request, "blog/home.html", ctx)


def tags_index(request):
    """
    /tags/ : 태그 목록 보드 (+ 태그 검색)
    """
    ctx = _base_context_for_home(request)

    q = (request.GET.get("q") or "").strip()
    is_searching = bool(q)

    tags = (
        Tag.objects
        .annotate(post_count=Count("posts", filter=Q(posts__is_published=True), distinct=True))
        .filter(post_count__gt=0)
    )

    if is_searching:
        # ✅ name/slug만 검색(보수적)
        tags = tags.filter(Q(name__icontains=q) | Q(slug__icontains=q))

    tags = tags.order_by("name")

    ctx.update({
        "board_view": "tags",
        "tags_mode": "index",
        "tags": tags,
        "selected_tag": None,

        "q": q,
        "is_searching": is_searching,
        "tags_count": tags.count(),
    })

    if is_htmx(request):
        return render(request, "blog/_board_tags.html", ctx)

    return render(request, "blog/home.html", ctx)


def tag_detail(request, tag_slug: str):
    """
    /tags/<tag>/ : 태그 상세(게시물 목록) 보드 (+ 검색 + 정렬)
    """
    ctx = _base_context_for_home(request)

    try:
        tag = Tag.objects.get(slug=tag_slug)
    except Tag.DoesNotExist:
        if is_htmx(request):
            resp = HttpResponse("", status=204)
            resp["HX-Redirect"] = "/tags/"
            return resp
        return redirect("/tags/")

    q = (request.GET.get("q") or "").strip()
    is_searching = bool(q)

    sort = (request.GET.get("sort") or "new").strip()
    sort_options = get_sort_options()
    sort_keys = {v for v, _ in sort_options}
    if sort not in sort_keys:
        sort = "new"

    posts_qs = (
        Post.objects
        .filter(is_published=True, tags=tag)
        .select_related("country")
        .prefetch_related("tags")
    )

    if is_searching:
        posts_qs = posts_qs.filter(Q(title__icontains=q) | Q(content__icontains=q))

    if sort == "old":
        posts_qs = posts_qs.order_by("published_at", "created_at", "id")
    elif sort == "title":
        posts_qs = posts_qs.order_by("title", "-published_at", "-created_at", "-id")
    else:
        posts_qs = posts_qs.order_by("-published_at", "-created_at", "-id")

    paginator = Paginator(posts_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page") or "1")
    posts = page_obj.object_list
    total = page_obj.paginator.count

    ctx.update({
        "board_view": "tags",
        "tags_mode": "detail",
        "selected_tag": tag,

        "q": q,
        "is_searching": is_searching,

        "sort": sort,
        "sort_options": sort_options,

        "posts": posts,
        "page_obj": page_obj,
        "tag_posts_total": total,
    })

    if is_htmx(request):
        return render(request, "blog/_board_tags.html", ctx)

    return render(request, "blog/home.html", ctx)
