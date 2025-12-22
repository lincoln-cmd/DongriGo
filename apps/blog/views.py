from __future__ import annotations

import re

from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.db.models import Q
from django.core.exceptions import FieldError

# ✅ admin live preview용
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required

from .models import Country, Post


def get_tabs():
    return [
        ("TRAVEL", "Travel", "travel"),
        ("HISTORY", "History", "history"),
        ("CULTURE", "Culture", "culture"),
        ("MY_LOG", "My Log", "my-log"),
    ]


def resolve_selected_category(category_slug: str | None):
    """
    URL의 category_slug(travel/history/...) -> Post.Category 값으로 매핑
    """
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
    """
    models.Post.used_image_ids()가 없을 때를 대비한 fallback.
    본문 안의 [[img:123]] 토큰을 찾아 이미지 id 목록을 반환.
    """
    if not content:
        return set()
    ids = set()
    for m in re.finditer(r"\[\[img:(\d+)\]\]", content):
        try:
            ids.add(int(m.group(1)))
        except Exception:
            pass
    return ids


@staff_member_required
@require_POST
def admin_live_preview(request):
    """
    Admin에서 작성 중인 content를 서버 렌더 결과와 동일하게 미리보기.
    - content: 본문 (필수)
    - post_id: 기존 글 수정 시(선택) -> 해당 Post의 images 관계를 써서 [[img:ID]]도 제대로 렌더되게 함
    """
    content = (request.POST.get("content") or "").strip()
    if content == "":
        return HttpResponse("", content_type="text/html; charset=utf-8")

    post_id = (request.POST.get("post_id") or "").strip()

    obj = None
    if post_id.isdigit():
        try:
            obj = Post.objects.prefetch_related("images").get(pk=int(post_id))
        except Post.DoesNotExist:
            obj = None

    if obj is None:
        # 새 글 작성 중: 임시 Post 객체로 렌더
        obj = Post(content=content)
    else:
        # 기존 글 수정: images 관계는 유지하고 본문만 교체
        obj.content = content

    html = obj.rendered_content()
    return HttpResponse(html, content_type="text/html; charset=utf-8")


def home(request, country_slug=None, category_slug=None, post_slug=None, **kwargs):
    """
    메인 화면
    - 좌: globe.gl
    - 우: HTMX로 #board 부분 갱신
    """

    # URLConf/호출 방식이 섞여도 안전하게 보정(이전 이슈 방지용)
    if country_slug is None:
        country_slug = kwargs.get("country_slug") or kwargs.get("slug") or kwargs.get("country")
    if category_slug is None:
        category_slug = kwargs.get("category_slug") or kwargs.get("cat") or kwargs.get("category")
    if post_slug is None:
        post_slug = kwargs.get("post_slug") or kwargs.get("post") or kwargs.get("postSlug")

    countries_qs = Country.objects.all()

    # globe.js로 내려줄 데이터
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
        # 필드 구성이 다를 때도 최소 동작 보장
        countries_for_globe = list(countries_qs.values("name", "slug"))

    selected_country = None
    if country_slug:
        try:
            selected_country = countries_qs.get(slug=country_slug)
        except Country.DoesNotExist:
            selected_country = None

    selected_category, selected_category_slug = resolve_selected_category(category_slug)

    # 게시물 목록
    posts_qs = Post.objects.filter(is_published=True, category=selected_category)
    if selected_country:
        posts_qs = posts_qs.filter(country=selected_country)

    q = (request.GET.get("q") or "").strip()
    if q:
        posts_qs = posts_qs.filter(Q(title__icontains=q) | Q(content__icontains=q))

    posts_qs = posts_qs.order_by("-published_at", "-created_at", "-id")

    paginator = Paginator(posts_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page") or "1")
    posts = page_obj.object_list

    selected_post = None
    selected_post_html = ""
    gallery_images = None

    # 상세
    if post_slug and selected_country:
        try:
            selected_post = (
                Post.objects
                .prefetch_related("images")
                .get(
                    country=selected_country,
                    category=selected_category,
                    slug=post_slug,
                    is_published=True,
                )
            )

            # 본문 렌더
            selected_post_html = selected_post.rendered_content()

            # 본문에 삽입된 이미지는 갤러리에서 제외
            if hasattr(selected_post, "used_image_ids") and callable(getattr(selected_post, "used_image_ids")):
                used_ids = set(selected_post.used_image_ids())
            else:
                used_ids = _extract_used_image_ids_from_content(selected_post.content)

            gallery_images = selected_post.images.exclude(id__in=used_ids)

        except Post.DoesNotExist:
            selected_post = None

    category_path = f"/{selected_country.slug}/{selected_category_slug}/" if selected_country else "/"

    context = {
        "countries": countries_qs,
        "countries_for_globe": countries_for_globe,
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
        "category_path": category_path,
    }

    # globe 클릭이 잘못된 slug를 보냈을 때: 보드 비우지 않게 204로 보수 처리
    if is_htmx(request) and country_slug and not selected_country:
        return HttpResponse("", status=204)

    if is_htmx(request):
        return render(request, "blog/_board.html", context)

    return render(request, "blog/home.html", context)
