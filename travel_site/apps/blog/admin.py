# admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Country, Post, PostImage


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1
    ordering = ("order", "id")

    # ✅ 복사 버튼 제거, "본문 삽입" 버튼만
    fields = ("id_display", "order", "image", "caption", "token", "insert_btn", "preview")
    readonly_fields = ("id_display", "token", "insert_btn", "preview")

    def id_display(self, obj):
        return obj.id if obj and obj.pk else "-"
    id_display.short_description = "ID"

    def token(self, obj):
        return f"[[img:{obj.id}]]" if obj and obj.pk else "(저장 후 생성)"
    token.short_description = "토큰"

    def insert_btn(self, obj):
        if not obj or not obj.pk:
            return "-"
        token = f"[[img:{obj.id}]]"
        return format_html(
            '<button type="button" class="button js-insert-token" data-token="{}">본문에 삽입</button>',
            token
        )
    insert_btn.short_description = "본문 삽입"

    def preview(self, obj):
        if not obj or not obj.image:
            return "-"
        return format_html(
            '<img src="{}" style="height:60px;border-radius:6px;" />',
            obj.image.url
        )
    preview.short_description = "미리보기"


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "country", "category", "is_published", "published_at", "updated_at")
    list_filter = ("country", "category", "is_published")
    search_fields = ("title", "content", "slug")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-published_at", "-created_at", "-id")
    date_hierarchy = "published_at"
    inlines = [PostImageInline]

    class Media:
        js = ("blog/js/admin_postimage_insert.js",)
