# apps/blog/urls.py
from django.urls import path
from . import views

app_name = "blog"

urlpatterns = [
    # admin live preview
    path("__admin/preview/", views.admin_live_preview, name="admin_live_preview"),

    # ✅ Phase 3: Tag pages (MUST be above country slug routes)
    path("tags/", views.tags_index, name="tags_index"),
    # IMPORTANT: use <str:...> to allow unicode tag slugs (e.g., '온천')
    path("tags/<str:tag_slug>/", views.tag_detail, name="tag_detail"),

    # main
    path("", views.home, name="home"),
    path("<slug:country_slug>/", views.home, name="country"),
    path("<slug:country_slug>/<slug:category_slug>/", views.home, name="category"),
    path("<slug:country_slug>/<slug:category_slug>/<str:post_slug>/", views.home, name="post"),
]
