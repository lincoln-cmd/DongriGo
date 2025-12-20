from django.urls import path
from . import views

app_name = "blog"

urlpatterns = [
    path("", views.home, name="home"),  # 기존 쿼리스트링 방식 유지(초기 화면)
    path("<slug:country_slug>/", views.home, name="country"),
    path("<slug:country_slug>/<slug:category_slug>/", views.home, name="category"),
    path("<slug:country_slug>/<slug:category_slug>/<slug:post_slug>/", views.home, name="post"),
]
