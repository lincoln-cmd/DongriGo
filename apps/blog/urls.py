# apps/blog/urls.py
from django.urls import path
from . import views

app_name = "blog"

urlpatterns = [
    # slug 라우트보다 위에 있어야 안전함
    path("__admin/preview/", views.admin_live_preview, name="admin_live_preview"),

    path("", views.home, name="home"),
    path("<slug:country_slug>/", views.home, name="country"),
    path("<slug:country_slug>/<slug:category_slug>/", views.home, name="category"),

    path("<slug:country_slug>/<slug:category_slug>/<str:post_slug>/", views.home, name="post"),
]
