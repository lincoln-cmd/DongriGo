from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.db.models import Q
from django.core.exceptions import FieldError

from .models import Country, Post, PostImage


def get_tabs():
    # key, label, url slug
    return [
        ("TRAVEL", "Travel", "travel"),
        ("HISTORY", "History", "history"),
        ("CULTURE", "Culture", "culture"),
        ("MY_LOG", "My Log", "my-log"),
    ]


def resolve_selected_category(category_slug: str | None):
    """
    URL slug(travel/history/...) -> Post.Category value
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


def is_htmx(request):
    return request.headers.get("HX-Request") == "true" or request.META.get("HTTP_HX_REQUEST") == "true"


def home(request, country_slug=None, category_slug=None, post_slug=None, **kwargs):
    """
    ✅ 중요: URLconf가 country_slug 같은 키워드 인자를 넘겨도 TypeError 안 나게 **kwargs로 흡수.
    (예: path("<slug:country_slug>/", views.home) 형태)
    """
    # 혹시 URL에서 다른 이름(slug 등)으로 들어오면 보정
    if country_slug is None:
        country_slug = kwargs.get("slug") or kwargs.get("country")
    if category_slug is None:
        category_slug = kwargs.get("cat") or kwargs.get("category")
    if post_slug is None:
        post_slug = kwargs.get("post") or kwargs.get("postSlug")

    # LEFT list
    countries_qs = Country.objects.all()

    # globe.js로 내려줄 데이터(매칭 강화를 위해 aliases/iso 포함)
    try:
        countries_for_globe = list(
            countries_qs.values("name", "name_ko", "name_en", "slug", "aliases", "iso_a2", "iso_a3")
        )
    except FieldError:
        # (혹시 아직 필드가 없다면 최소 동작)
        countries_for_globe = list(countries_qs.values("name", "slug"))

    selected_country = None
    if country_slug:
        try:
            selected_country = countries_qs.get(slug=country_slug)
        except Country.DoesNotExist:
            selected_country = None

    # category
    selected_category, selected_category_slug = resolve_selected_category(category_slug)

    # posts query
    posts_qs = Post.objects.filter(is_published=True)
    if selected_country:
        posts_qs = posts_qs.filter(country=selected_country)
    posts_qs = posts_qs.filter(category=selected_category)

    q = (request.GET.get("q") or "").strip()
    if q:
        posts_qs = posts_qs.filter(Q(title__icontains=q) | Q(content__icontains=q))

    posts_qs = posts_qs.order_by("-published_at", "-created_at", "-id")

    # pagination
    page = request.GET.get("page") or "1"
    paginator = Paginator(posts_qs, 10)
    page_obj = paginator.get_page(page)
    posts = page_obj.object_list

    selected_post = None
    selected_post_html = ""
    gallery_images = None

    if post_slug and selected_country:
        try:
            selected_post = Post.objects.get(
                country=selected_country,
                category=selected_category,
                slug=post_slug,
                is_published=True,
            )
            selected_post_html = selected_post.rendered_content()
            gallery_images = PostImage.objects.filter(post=selected_post).order_by("order", "id")
        except Post.DoesNotExist:
            selected_post = None

    # category_path (board 내부 링크들이 사용하는 base path)
    if selected_country:
        category_path = f"/{selected_country.slug}/{selected_category_slug}/"
    else:
        category_path = "/"

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

    # slug가 틀린 경우 HTMX면 보드를 "빈 내용으로 교체"하지 않도록 204 처리
    if is_htmx(request) and country_slug and not selected_country:
        return HttpResponse("", status=204)

    if is_htmx(request):
        return render(request, "blog/_board.html", context)

    return render(request, "blog/home.html", context)
