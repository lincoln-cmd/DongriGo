from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.utils import timezone
from django.utils.safestring import mark_safe

from .models import Country, Post, PostImage
import re


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

    # ✅ Country 전용 actions 추가 (PostAdmin.actions와는 별개)
    actions = ("action_normalize_country_fields", "action_autofill_aliases")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # ✅ posts_count N+1 방지
        return qs.annotate(posts_total=Count("posts", distinct=True))

    def posts_count(self, obj: Country):
        return getattr(obj, "posts_total", 0)
    posts_count.short_description = "Posts"
    posts_count.admin_order_field = "posts_total"

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

    # -------------------------
    # ✅ actions 구현
    # -------------------------
    @admin.action(description="선택 국가: ISO/slug/name 공백 정규화")
    def action_normalize_country_fields(self, request, queryset):
        updated = 0
        for c in queryset:
            changed = False

            # iso 정규화(대문자 + 공백 제거)
            if getattr(c, "iso_a2", None):
                v = (c.iso_a2 or "").strip().upper()
                if c.iso_a2 != v:
                    c.iso_a2 = v
                    changed = True

            if getattr(c, "iso_a3", None):
                v = (c.iso_a3 or "").strip().upper()
                if c.iso_a3 != v:
                    c.iso_a3 = v
                    changed = True

            # slug 공백 제거
            if getattr(c, "slug", None):
                v = (c.slug or "").strip()
                if c.slug != v:
                    c.slug = v
                    changed = True

            # name 공백 정리(연속 공백 -> 1개)
            if getattr(c, "name", None):
                v = re.sub(r"\s+", " ", (c.name or "")).strip()
                if c.name != v:
                    c.name = v
                    changed = True

            if changed:
                c.save()
                updated += 1

        self.message_user(request, f"{updated}개 국가를 정규화했습니다.")

    @admin.action(description="선택 국가: aliases 자동 보강(name/name_en/괄호영문)")
    def action_autofill_aliases(self, request, queryset):
        updated = 0

        def extract_paren_en(display_name: str) -> str:
            m = re.search(r"\(([^)]+)\)", display_name or "")
            return (m.group(1).strip() if m else "")

        def split_aliases(s: str) -> list[str]:
            if not s:
                return []
            parts = re.split(r"[,;|]", s)
            return [p.strip() for p in parts if p.strip()]

        for c in queryset:
            before = (getattr(c, "aliases", "") or "").strip()
            items = set(split_aliases(before))

            nm = (getattr(c, "name", "") or "").strip()
            nm_en = (getattr(c, "name_en", "") or "").strip()
            paren = extract_paren_en(nm)

            for v in (nm, nm_en, paren):
                v = (v or "").strip()
                if v and v not in items:
                    items.add(v)

            after = ", ".join(sorted(items))
            if after != before:
                c.aliases = after
                c.save(update_fields=["aliases"])
                updated += 1

        self.message_user(request, f"{updated}개 국가의 aliases를 보강했습니다.")


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
    list_editable = ("is_published",)

    list_display = (
        "title",
        "slug",
        "country",
        "category",
        "is_published",
        "published_at",
        "updated_at",
        "images_count",
        "cover_preview",
        "view_on_site_link",
    )
    list_filter = ("country", "category", "is_published", "published_at")
    search_fields = (
        "title",
        "content",
        "slug",
        "country__name",
        "country__slug",
    )
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-published_at", "-created_at", "-id")
    date_hierarchy = "published_at"
    list_select_related = ("country",)
    list_per_page = 50

    autocomplete_fields = ("country",)
    inlines = [PostImageInline]

    # ✅ Post 전용 actions(발행/비공개) 유지
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
        # ✅ images_count N+1 방지
        return qs.annotate(images_total=Count("images", distinct=True)).prefetch_related("images")

    def images_count(self, obj: Post):
        return getattr(obj, "images_total", 0)
    images_count.short_description = "Images"
    images_count.admin_order_field = "images_total"

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
        html = obj.rendered_content()
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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # ✅ slug를 비워도 통과하도록(저장 시 model.save()에서 자동 생성)
        if "slug" in form.base_fields:
            form.base_fields["slug"].required = False
        return form

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        post = form.instance

        imgs = list(post.images.all().order_by("order", "id"))
        if not imgs:
            return

        changed = False
        for idx, img in enumerate(imgs):
            new_order = idx * 10
            if img.order != new_order:
                img.order = new_order
                changed = True

        if changed:
            PostImage.objects.bulk_update(imgs, ["order"])

    class Media:
        css = {"all": ("blog/css/admin_extra.css",)}
        js = (
            "blog/js/admin_postimage_insert.js",
            "blog/js/admin_live_preview.js",
            "blog/js/admin_markdown_toolbar.js",
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
