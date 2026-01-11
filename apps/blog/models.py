from django.db import models
from django.utils import timezone
from django.utils.text import slugify  # ✅ 필수: defaultfilters.slugify 금지

import markdown as md
import bleach
import re
import html
from django.db.models import Max
from django.db import IntegrityError


class Country(models.Model):
    name = models.CharField(max_length=100)          # 예: 대한민국(Korea)
    slug = models.SlugField(unique=True)             # 예: korea / japan

    iso_a2 = models.CharField(max_length=2, blank=True, null=True, db_index=True)   # KR
    iso_a3 = models.CharField(max_length=3, blank=True, null=True, unique=True)     # KOR
    name_ko = models.CharField(max_length=100, blank=True, default="")              # 대한민국
    name_en = models.CharField(max_length=100, blank=True, default="")              # Korea
    aliases = models.TextField(blank=True, default="")                               # South Korea, Republic of Korea ...

    short_description = models.CharField(max_length=300, blank=True)
    flag_image = models.ImageField(upload_to="flags/", blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"/{self.slug}/"

    @staticmethod
    def _unique_slugify(model_cls, base: str, *, instance_pk=None, max_len: int = 50) -> str:
        """
        base 로 slug 후보를 만들고, 충돌 시 -2, -3... 붙여서 유니크하게 만든다.
        (필드 추가/마이그레이션 없이 admin/seed 실수 방지용)
        """
        base = (base or "").strip()
        s = slugify(base)
        if not s:
            s = slugify(base, allow_unicode=True)
        s = (s or "country")[:max_len]

        candidate = s
        n = 2
        while True:
            qs = model_cls.objects.filter(slug=candidate)
            if instance_pk is not None:
                qs = qs.exclude(pk=instance_pk)
            if not qs.exists():
                return candidate

            suffix = f"-{n}"
            cut = max_len - len(suffix)
            candidate = (s[:cut] if cut > 0 else s) + suffix
            n += 1

    def save(self, *args, **kwargs):
        # ✅ ISO 값 정규화
        if self.iso_a2 is not None:
            v = (self.iso_a2 or "").strip().upper()
            self.iso_a2 = v or None
        if self.iso_a3 is not None:
            v = (self.iso_a3 or "").strip().upper()
            self.iso_a3 = v or None

        # ✅ slug 비어있을 때만 자동 생성(기존 값 보존) + 유니크 보장
        if not (self.slug or "").strip():
            base = (self.name_en or self.name or "").strip()
            self.slug = self._unique_slugify(Country, base, instance_pk=self.pk, max_len=50)

        super().save(*args, **kwargs)


class Tag(models.Model):
    """
    Phase 3 (minimal): Tag system
    - created_at 없음(현재 DB 에러 원인 제거)
    """
    name = models.CharField(max_length=50, unique=True)
    # ✅ Unicode slug 허용 (예: '온천')
    slug = models.SlugField(max_length=60, unique=True, allow_unicode=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @staticmethod
    def _unique_slugify(base: str, *, instance_pk=None, max_len: int = 60) -> str:
        base = (base or "").strip()
        s = slugify(base)
        if not s:
            s = slugify(base, allow_unicode=True)
        s = (s or "tag")[:max_len]

        candidate = s
        n = 2
        while True:
            qs = Tag.objects.filter(slug=candidate)
            if instance_pk is not None:
                qs = qs.exclude(pk=instance_pk)
            if not qs.exists():
                return candidate

            suffix = f"-{n}"
            cut = max_len - len(suffix)
            candidate = (s[:cut] if cut > 0 else s) + suffix
            n += 1

    def save(self, *args, **kwargs):
        """
        - slug 변경 시 TagSlugHistory에 이전 slug 저장
        - old_slug가 현재 다른 Tag의 slug로 쓰이고 있으면(충돌) history 저장을 건너뜀(보수적)
        """
        old_slug = None
        if self.pk:
            old = Tag.objects.filter(pk=self.pk).values("slug").first()
            if old:
                old_slug = old.get("slug")

        if not (self.slug or "").strip():
            self.slug = self._unique_slugify(self.name, instance_pk=self.pk, max_len=60)

        super().save(*args, **kwargs)

        if self.pk and old_slug and (old_slug != self.slug):
            old_slug = (old_slug or "").strip()
            if old_slug:
                # 다른 태그가 현재 slug로 사용 중이면 redirect ambiguity 방지 위해 기록하지 않음
                if Tag.objects.filter(slug=old_slug).exclude(pk=self.pk).exists():
                    return
                try:
                    TagSlugHistory.objects.get_or_create(
                        old_slug=old_slug,
                        defaults={"tag": self},
                    )
                except IntegrityError:
                    pass


class TagSlugHistory(models.Model):
    """
    Tag slug 변경 이력:
    - /tags/<old_slug>/ 접근 시 canonical(/tags/<tag.slug>/)로 redirect 하기 위함
    """
    tag = models.ForeignKey("Tag", on_delete=models.CASCADE, related_name="slug_history")
    old_slug = models.CharField(max_length=60, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.old_slug} -> {self.tag.slug}"


class Post(models.Model):
    class Category(models.TextChoices):
        HISTORY = "HISTORY", "History"
        CULTURE = "CULTURE", "Culture"
        TRAVEL = "TRAVEL", "Travel"
        MY_LOG = "MY_LOG", "My Log"

    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="posts")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.TRAVEL)

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)

    # ✅ Phase 3: tags
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")

    content = models.TextField(
        blank=True,
        help_text="이미지 삽입: [[img:123]] (Post Images의 ID 사용). 코드블럭(```) 안에서는 치환되지 않습니다."
    )

    cover_image = models.ImageField(upload_to="posts/", blank=True, null=True)

    is_published = models.BooleanField(default=True)
    published_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at", "-id"]

    def __str__(self):
        return f"[{self.category}] {self.title}"

    @property
    def category_slug(self) -> str:
        mapping = {
            self.Category.TRAVEL: "travel",
            self.Category.HISTORY: "history",
            self.Category.CULTURE: "culture",
            self.Category.MY_LOG: "my-log",
        }
        return mapping.get(self.category, "travel")

    def get_absolute_url(self):
        return f"/{self.country.slug}/{self.category_slug}/{self.slug}/"

    # -------------------------
    # [[img:123]] token replace
    # -------------------------
    _IMG_TOKEN_RE = re.compile(r"\[\[img:(\d+)\]\]")
    _FENCED_CODE_RE = re.compile(r"(```.*?```)", re.DOTALL)

    @staticmethod
    def _unique_slugify(model_cls, base: str, *, instance_pk=None, max_len: int = 220) -> str:
        """
        base 로 slug 후보를 만들고, 충돌 시 -2, -3... 붙여서 유니크하게 만든다.
        """
        base = (base or "").strip()
        s = slugify(base)
        if not s:
            s = slugify(base, allow_unicode=True)
        s = (s or "post")[:max_len]

        candidate = s
        n = 2
        while True:
            qs = model_cls.objects.filter(slug=candidate)
            if instance_pk is not None:
                qs = qs.exclude(pk=instance_pk)
            if not qs.exists():
                return candidate

            suffix = f"-{n}"
            cut = max_len - len(suffix)
            candidate = (s[:cut] if cut > 0 else s) + suffix
            n += 1

    def save(self, *args, **kwargs):
        """
        - slug/country/category 변경 시 PostSlugHistory에 이전 조합 저장
        """
        old_slug = None
        old_country_id = None
        old_category = None

        if self.pk:
            old = Post.objects.filter(pk=self.pk).values("slug", "country_id", "category").first()
            if old:
                old_slug = old.get("slug")
                old_country_id = old.get("country_id")
                old_category = old.get("category")

        if not self.slug:
            self.slug = self._unique_slugify(Post, self.title, instance_pk=self.pk)

        if self.is_published and not self.published_at:
            self.published_at = timezone.localdate()

        super().save(*args, **kwargs)

        if self.pk and old_slug and old_country_id and old_category:
            old_key = (old_country_id, old_category, old_slug)
            new_key = (self.country_id, self.category, self.slug)
            if old_key != new_key:
                try:
                    PostSlugHistory.objects.get_or_create(
                        country_id=old_country_id,
                        category=old_category,
                        old_slug=old_slug,
                        defaults={"post": self},
                    )
                except IntegrityError:
                    pass

    def _replace_img_tokens_outside_codeblocks(self, text: str) -> str:
        if not text:
            return ""

        images_by_id = {str(img.id): img for img in self.images.all()}

        def repl(match: re.Match) -> str:
            img_id = match.group(1)
            img = images_by_id.get(img_id)
            if not img:
                return match.group(0)

            src = getattr(img.image, "url", "") or ""
            caption_raw = (img.caption or "").strip()

            src_esc = html.escape(src, quote=True)
            cap_esc = html.escape(caption_raw, quote=True)

            figcap = f'<figcaption class="hint">{html.escape(caption_raw)}</figcaption>' if caption_raw else ""
            return (
                '<figure class="post-image">'
                f'<img class="post-inline-img" src="{src_esc}" alt="{cap_esc}" loading="lazy" decoding="async" '
                f'data-full="{src_esc}" data-caption="{cap_esc}" />'
                f"{figcap}"
                "</figure>"
            )

        parts = self._FENCED_CODE_RE.split(text)
        out = []
        for part in parts:
            if part.startswith("```") and part.endswith("```"):
                out.append(part)
            else:
                out.append(self._IMG_TOKEN_RE.sub(repl, part))
        return "".join(out)

    def used_image_ids(self) -> set[int]:
        text = self.content or ""
        if not text:
            return set()

        ids: set[int] = set()
        parts = self._FENCED_CODE_RE.split(text)
        for part in parts:
            if part.startswith("```") and part.endswith("```"):
                continue
            for m in self._IMG_TOKEN_RE.finditer(part):
                try:
                    ids.add(int(m.group(1)))
                except Exception:
                    pass
        return ids

    def rendered_content(self) -> str:
        src_md = self._replace_img_tokens_outside_codeblocks(self.content or "")

        raw_html = md.markdown(
            src_md,
            extensions=["fenced_code", "tables", "nl2br"],
            output_format="html5",
        )

        allowed_tags = bleach.sanitizer.ALLOWED_TAGS.union({
            "p", "br", "hr",
            "h1", "h2", "h3", "h4",
            "ul", "ol", "li",
            "blockquote",
            "pre", "code",
            "table", "thead", "tbody", "tr", "th", "td",
            "img",
            "figure", "figcaption",
        })

        allowed_attrs = {
            **bleach.sanitizer.ALLOWED_ATTRIBUTES,
            "a": ["href", "title", "target", "rel"],
            "img": ["src", "alt", "title", "class", "loading", "decoding", "width", "height", "data-full", "data-caption"],
            "figure": ["class"],
            "figcaption": ["class"],
            "th": ["align"],
            "td": ["align"],
        }

        cleaned = bleach.clean(
            raw_html,
            tags=allowed_tags,
            attributes=allowed_attrs,
            protocols=["http", "https", "mailto"],
            strip=True,
        )

        cleaned = cleaned.replace("<a ", '<a rel="nofollow noopener" target="_blank" ')
        return cleaned


class PostImage(models.Model):
    post = models.ForeignKey(
        "Post",
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="post_images/")
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        cap = (self.caption or "").strip()
        return f"{self.post_id} - {self.order}" + (f" ({cap})" if cap else "")

    def save(self, *args, **kwargs):
        if self.pk is None and (self.order is None or self.order == 0):
            max_order = (
                PostImage.objects.filter(post=self.post)
                .aggregate(m=Max("order"))
                .get("m")
            )
            self.order = (max_order or 0) + 10
        super().save(*args, **kwargs)


class SeedMeta(models.Model):
    """Seed(초기 데이터) 적용 이력을 1-row로 기록해 재시딩을 안전하게 만든다."""

    name = models.CharField(max_length=50, unique=True, default="prod_seed")
    fixture_path = models.CharField(max_length=300, blank=True, default="")
    fixture_sha256 = models.CharField(max_length=64, blank=True, default="")
    applied_at = models.DateTimeField(null=True, blank=True)
    notes = models.JSONField(blank=True, default=dict)

    class Meta:
        verbose_name = "Seed Meta"
        verbose_name_plural = "Seed Meta"

    def __str__(self):
        return f"{self.name} ({self.fixture_sha256[:8] if self.fixture_sha256 else 'no-hash'})"


class PostSlugHistory(models.Model):
    post = models.ForeignKey("Post", on_delete=models.CASCADE, related_name="slug_history")
    country = models.ForeignKey("Country", on_delete=models.CASCADE, related_name="post_slug_history")
    category = models.CharField(max_length=20)
    old_slug = models.SlugField(max_length=220, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["country", "category", "old_slug"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["country", "category", "old_slug"], name="uniq_oldslug_per_country_cat"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.country.slug}/{self.category}:{self.old_slug} -> post:{self.post_id}"
