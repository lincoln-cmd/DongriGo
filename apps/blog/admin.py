from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.utils.safestring import mark_safe

from .models import Country, Post, PostImage


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "iso_a2",
        "iso_a3",
        "name_ko",
        "name_en",
        "posts_count",
        "view_on_site_link",
        "flag_preview",
    )
    search_fields = ("name", "slug", "iso_a2", "iso_a3", "aliases", "name_ko", "name_en")
    list_filter = ("iso_a2",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    list_per_page = 50

    def posts_count(self, obj: Country):
        # 주의: admin_order_field는 annotation 없으면 잘못 동작할 수 있어 생략
        return obj.posts.count()
    posts_count.short_description = "Posts"

    def view_on_site_link(self, obj: Country):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">열기</a>',
            obj.get_absolute_url()
        )
    view_on_site_link.short_description = "Site"

    def flag_preview(self, obj: Country):
        if not getattr(obj, "flag_image", None):
            return "-"
        try:
            return format_html(
                '<img src="{}" style="height:18px;border-radius:4px;" />',
                obj.flag_image.url
            )
        except Exception:
            return "-"
    flag_preview.short_description = "Flag"


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1
    ordering = ("order", "id")

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
        if not obj or not getattr(obj, "image", None):
            return "-"
        try:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:6px;" />',
                obj.image.url
            )
        except Exception:
            return "-"
    preview.short_description = "미리보기"


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "country",
        "category",
        "is_published",
        "published_at",
        "updated_at",
        "images_count",
        "cover_preview",
        "view_on_site_link",
    )
    list_filter = ("country", "category", "is_published")
    search_fields = ("title", "content", "slug")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-published_at", "-created_at", "-id")
    date_hierarchy = "published_at"
    list_select_related = ("country",)
    list_per_page = 50

    autocomplete_fields = ("country",)
    inlines = [PostImageInline]

    actions = ("action_publish", "action_unpublish")

    fieldsets = (
        ("기본", {"fields": ("country", "category", "title", "slug")}),
        ("콘텐츠", {"fields": ("content", "rendered_preview")}),
        ("미디어", {"fields": ("cover_image",)}),
        ("발행", {"fields": ("is_published", "published_at")}),
        ("메타", {"fields": ("created_at", "updated_at")}),
    )

    readonly_fields = ("rendered_preview", "created_at", "updated_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("images")

    def images_count(self, obj: Post):
        return obj.images.count()
    images_count.short_description = "Images"

    def cover_preview(self, obj: Post):
        if not getattr(obj, "cover_image", None):
            return "-"
        try:
            return format_html(
                '<img src="{}" style="height:28px;border-radius:6px;" />',
                obj.cover_image.url
            )
        except Exception:
            return "-"
    cover_preview.short_description = "Cover"

    def view_on_site_link(self, obj: Post):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">열기</a>',
            obj.get_absolute_url()
        )
    view_on_site_link.short_description = "Site"

    def rendered_preview(self, obj: Post):
        if not obj or not obj.pk:
            return "저장 후 미리보기가 표시됩니다."
        html = obj.rendered_content()  # bleach로 정제된 HTML 가정
        return format_html(
            '<div style="max-height:280px;overflow:auto;border:1px solid #ddd;padding:10px;border-radius:8px;">{}</div>',
            mark_safe(html),
        )
    rendered_preview.short_description = "본문 미리보기"

    @admin.action(description="선택 글 발행(오늘 날짜 자동 설정)")
    def action_publish(self, request, queryset):
        today = timezone.localdate()
        updated = 0
        for p in queryset:
            if not p.is_published:
                p.is_published = True
            if not p.published_at:
                p.published_at = today
            p.save(update_fields=["is_published", "published_at", "updated_at"])
            updated += 1
        self.message_user(request, f"{updated}개 글을 발행 처리했습니다.")

    @admin.action(description="선택 글 비공개")
    def action_unpublish(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f"{updated}개 글을 비공개 처리했습니다.")

    class Media:
        css = {"all": ("blog/css/admin_extra.css",)}
        js = (
            "blog/js/admin_postimage_insert.js",
            "blog/js/admin_live_preview.js",
            "blog/js/admin_markdown_toolbar.js",  # ✅ 추가
        )


@admin.register(PostImage)
class PostImageAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "order", "caption", "thumb", "created_at")
    list_filter = ("created_at",)
    search_fields = ("caption", "post__title", "post__slug", "post__country__name", "post__country__slug")
    ordering = ("-created_at", "-id")
    autocomplete_fields = ("post",)

    def thumb(self, obj: PostImage):
        if not getattr(obj, "image", None):
            return "-"
        try:
            return format_html(
                '<img src="{}" style="height:28px;border-radius:6px;" />',
                obj.image.url
            )
        except Exception:
            return "-"
    thumb.short_description = "Preview"
