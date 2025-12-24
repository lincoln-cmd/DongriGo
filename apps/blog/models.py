from django.db import models
from django.utils import timezone
from django.utils.text import slugify

import markdown as md
import bleach
import re
import html
from django.db.models import Max


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
        s = slugify(base)  # 기본은 ascii slug
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
        # - admin/폼에서 빈 값이 ""로 들어오면(=falsy) 기존 로직이 작동하지 않아 ""가 DB에 저장될 수 있음
        # - 특히 iso_a3(unique=True)는 ""가 여러 행에 저장되면 UNIQUE 충돌 위험이 커서 "" -> None 으로 정규화
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
        (필드 추가/마이그레이션 없이 admin 실수 방지용)
        """
        base = (base or "").strip()
        s = slugify(base)  # 보통 영어/숫자면 이게 제일 깔끔
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
        # ✅ slug 비어있으면 자동 생성(중복이면 -2, -3…)
        if not self.slug:
            self.slug = self._unique_slugify(Post, self.title, instance_pk=self.pk)

        # ✅ 발행글인데 published_at이 비어있으면 오늘로 자동 세팅
        if self.is_published and not self.published_at:
            self.published_at = timezone.localdate()

        super().save(*args, **kwargs)

    def _replace_img_tokens_outside_codeblocks(self, text: str) -> str:
        """
        - ``` fenced code block 내부는 치환하지 않음
        - 토큰이 현재 Post의 PostImage(id)와 매칭되지 않으면 그대로 둠(보수적)
        """
        if not text:
            return ""

        # 현재 포스트에 연결된 이미지만 허용(보안/운영상 안전)
        images_by_id = {str(img.id): img for img in self.images.all()}

        def repl(match: re.Match) -> str:
            img_id = match.group(1)
            img = images_by_id.get(img_id)
            if not img:
                return match.group(0)

            src = getattr(img.image, "url", "") or ""
            caption_raw = (img.caption or "").strip()

            # ✅ attribute 안전성: 따옴표/특수문자 대비해서 escape
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
                out.append(part)  # 코드블럭은 그대로
            else:
                out.append(self._IMG_TOKEN_RE.sub(repl, part))
        return "".join(out)

    def used_image_ids(self) -> set[int]:
        """
        본문에 [[img:123]] 형태로 '사용된' 이미지 id를 추출.
        ``` fenced code block 내부는 제외(치환 규칙과 동일)
        """
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
        # 1) 토큰 치환(코드블럭 제외)
        src_md = self._replace_img_tokens_outside_codeblocks(self.content or "")

        # 2) markdown -> html
        raw_html = md.markdown(
            src_md,
            extensions=["fenced_code", "tables", "nl2br"],
            output_format="html5",
        )

        # 3) sanitize(허용 태그/속성 확장: figure/figcaption + img class/data-*)
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

        # 링크는 새탭 + nofollow/noopener 강제
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
        """
        신규 이미지 생성 시 order가 0이면 자동으로 '맨 뒤'에 배치.
        - 이미 order를 수동 지정한 경우엔 그대로 존중
        - 기존 레코드 수정 시엔 건드리지 않음
        """
        if self.pk is None and (self.order is None or self.order == 0):
            max_order = (
                PostImage.objects.filter(post=self.post)
                .aggregate(m=Max("order"))
                .get("m")
            )
            self.order = (max_order or 0) + 10  # 10 단위로 띄워두면 중간 삽입이 편함
        super().save(*args, **kwargs)
