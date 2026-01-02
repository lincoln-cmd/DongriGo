from django.contrib import admin, messages
from django.db.models import Count
from django.utils.html import format_html
from django.utils import timezone
from django.utils.safestring import mark_safe
from django import forms
from django.core.exceptions import ValidationError

from .models import Country, Post, PostImage, Tag
try:
    from .models import PostSlugHistory
except Exception:
    PostSlugHistory = None

import re


def _normalize_aliases(raw: str) -> str:
    """aliases를 'comma+space' 포맷으로 정규화."""
    if not raw:
        return ""
    parts = re.split(r"[,;|\n]+", raw)
    items = [p.strip() for p in parts if p.strip()]
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return ", ".join(out)


class CountryAdminForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = "__all__"

    def clean_iso_a2(self):
        v = (self.cleaned_data.get("iso_a2") or "").strip().upper()
        if v == "":
            return None
        if len(v) != 2:
            raise ValidationError("iso_a2는 2자리여야 합니다. (예: KR)")
        return v

    def clean_iso_a3(self):
        v = (self.cleaned_data.get("iso_a3") or "").strip().upper()
        if v == "":
            return None
        if len(v) != 3:
            raise ValidationError("iso_a3는 3자리여야 합니다. (예: KOR)")
        return v

    def clean_aliases(self):
        raw = self.cleaned_data.get("aliases") or ""
        return _normalize_aliases(raw)


class PostAdminForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 모델 save에서 slug 자동 생성하므로 admin에서 빈 값 허용
        if "slug" in self.fields:
            self.fields["slug"].required = False

    def clean_slug(self):
        return (self.cleaned_data.get("slug") or "").strip()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """
    ✅ Tag는 created_at 없이 최소 운영
    - created_at 정렬/표시 금지(현재 DB 에러 원인 제거)
    """
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    ordering = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 50


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    form = CountryAdminForm

    list_display = (
        "name",
        "slug",
        "iso_a2",
        "iso_a3",
        "name_ko",
        "name_en",
        "data_warnings",
        "posts_count",
        "view_on_site_link",
        "flag_preview",
    )
    search_fields = ("name", "slug", "iso_a2", "iso_a3", "aliases", "name_ko", "name_en")
    list_filter = ("iso_a2",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    list_per_page = 50

    actions = ("action_normalize_country_fields", "action_autofill_aliases")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(posts_total=Count("posts", distinct=True))

    def posts_count(self, obj: Country):
        return getattr(obj, "posts_total", 0)
    posts_count.short_description = "Posts"
    posts_count.admin_order_field = "posts_total"

    def data_warnings(self, obj: Country):
        issues = []
        if obj.iso_a2 and len(obj.iso_a2) != 2:
            issues.append("iso_a2")
        if obj.iso_a3 and len(obj.iso_a3) != 3:
            issues.append("iso_a3")

        raw = (getattr(obj, "aliases", "") or "").strip()
        if raw and _normalize_aliases(raw) != raw:
            issues.append("aliases")

        if not issues:
            return mark_safe('<span style="color:#2e7d32;">OK</span>')

        return format_html(
            '<span title="{}" style="color:#d32f2f;font-weight:700;">⚠ {}</span>',
            ", ".join(issues),
            len(issues),
        )
    data_warnings.short_description = "Check"

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
                '<img src="{}" style="height:22px;border-radius:4px;border:1px solid #ddd;" />',
                obj.flag_image.url
            )
        except Exception:
            return "-"
    flag_preview.short_description = "Flag"

    def save_model(self, request, obj, form, change):
        before_aliases = ""
        before_iso_a2 = None
        before_iso_a3 = None
        if change and obj.pk:
            old = Country.objects.filter(pk=obj.pk).values("aliases", "iso_a2", "iso_a3").first()
            if old:
                before_aliases = (old.get("aliases") or "").strip()
                before_iso_a2 = old.get("iso_a2")
                before_iso_a3 = old.get("iso_a3")

        super().save_model(request, obj, form, change)

        after_aliases = (getattr(obj, "aliases", "") or "").strip()
        if after_aliases and before_aliases and after_aliases != before_aliases:
            messages.info(request, f"[Country] aliases 정규화 적용: '{before_aliases}' → '{after_aliases}'")
        if before_iso_a2 is not None and before_iso_a2 != obj.iso_a2:
            messages.info(request, f"[Country] iso_a2 변경: {before_iso_a2} → {obj.iso_a2}")
        if before_iso_a3 is not None and before_iso_a3 != obj.iso_a3:
            messages.info(request, f"[Country] iso_a3 변경: {before_iso_a3} → {obj.iso_a3}")

    @admin.action(description="선택 국가: ISO/slug/name 공백 정규화")
    def action_normalize_country_fields(self, request, queryset):
        updated = 0
        for c in queryset:
            changed = False

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

            for fld in ("name", "name_ko", "name_en"):
                if hasattr(c, fld):
                    v = (getattr(c, fld) or "").strip()
                    if getattr(c, fld) != v:
                        setattr(c, fld, v)
                        changed = True

            if getattr(c, "slug", None):
                v = (c.slug or "").strip()
                if c.slug != v:
                    c.slug = v
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
    form = PostAdminForm

    list_editable = ("is_published",)

    list_display = (
        "title",
        "slug",
        "country",
        "category",
        "is_published",
        "published_at",
        "updated_at",
        "data_warnings",
        "images_count",
        "cover_preview",
        "view_on_site_link",
    )
    list_filter = ("country", "category", "is_published", "tags")
    search_fields = ("title", "slug", "content", "tags__name", "tags__slug")
    ordering = ("-published_at", "-created_at", "-id")
    list_per_page = 50

    autocomplete_fields = ("country",)
    filter_horizontal = ("tags",)

    inlines = [PostImageInline]

    actions = ("action_publish", "action_unpublish")

    fieldsets = (
        ("기본", {"fields": ("country", "category", "title", "slug", "tags")}),
        ("콘텐츠", {"fields": ("content", "rendered_preview")}),
        ("미디어", {"fields": ("cover_image",)}),
        ("발행", {"fields": ("is_published", "published_at")}),
        ("메타", {"fields": ("created_at", "updated_at")}),
    )

    readonly_fields = ("rendered_preview", "created_at", "updated_at")

    def data_warnings(self, obj: Post):
        issues = []
        if obj.is_published and not obj.published_at:
            issues.append("published_at")
        if PostSlugHistory is not None:
            try:
                if obj.pk and PostSlugHistory.objects.filter(post=obj).exists():
                    issues.append("slug_history")
            except Exception:
                pass

        if not issues:
            return mark_safe('<span style="color:#2e7d32;">OK</span>')

        return format_html(
            '<span title="{}" style="color:#d32f2f;font-weight:700;">⚠ {}</span>',
            ", ".join(issues),
            len(issues),
        )
    data_warnings.short_description = "Check"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(images_total=Count("images", distinct=True)).prefetch_related("images", "tags")

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
        html2 = obj.rendered_content()
        return format_html(
            '<div style="max-height:280px;overflow:auto;border:1px solid #ddd;padding:10px;border-radius:8px;">{}</div>',
            mark_safe(html2),
        )
    rendered_preview.short_description = "본문 미리보기"

    def save_model(self, request, obj, form, change):
        old_slug = None
        old_country_id = None
        old_category = None
        if change and obj.pk:
            old = Post.objects.filter(pk=obj.pk).values("slug", "country_id", "category").first()
            if old:
                old_slug = old.get("slug")
                old_country_id = old.get("country_id")
                old_category = old.get("category")

        super().save_model(request, obj, form, change)

        if not (form.cleaned_data.get("slug") or "").strip():
            messages.info(request, "[Post] slug가 비어 있어 title 기반으로 자동 생성되었습니다.")

        if old_slug and (old_slug != obj.slug or old_country_id != obj.country_id or old_category != obj.category):
            messages.warning(
                request,
                f"[Post] URL 식별자가 변경되었습니다. 이전 링크({old_slug})는 301 리다이렉트로 보존됩니다."
            )

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
        self.message_user(request, f"{updated}개 글을 발행했습니다.")

    @admin.action(description="선택 글 비공개")
    def action_unpublish(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f"{updated}개 글을 비공개로 변경했습니다.")

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        obj: Post = form.instance
        imgs = list(obj.images.order_by("order", "id"))
        changed2 = False
        current = 10
        for im in imgs:
            if im.order != current:
                im.order = current
                current += 10
                changed2 = True
            else:
                current += 10

        if changed2:
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
    list_filter = ("post",)
    search_fields = ("caption", "post__title")
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
