from django.db import models
from django.utils import timezone
import markdown as md
import bleach


class Country(models.Model):
    # ✅ 표시용(템플릿에서 그대로 쓰던 필드)
    name = models.CharField(max_length=100)          # 예: 대한민국(Korea)
    slug = models.SlugField(unique=True)             # 예: korea / japan

    # ✅ 자동 시딩/매핑 안정용
    iso_a2 = models.CharField(max_length=2, blank=True, null=True, db_index=True)   # KR
    iso_a3 = models.CharField(max_length=3, blank=True, null=True, unique=True)     # KOR (unique 추천)
    name_ko = models.CharField(max_length=100, blank=True, default="")              # 대한민국
    name_en = models.CharField(max_length=100, blank=True, default="")              # Korea
    aliases = models.TextField(blank=True, default="")                               # South Korea, Republic of Korea ...

    short_description = models.CharField(max_length=300, blank=True)
    flag_image = models.ImageField(upload_to="flags/", blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


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

    def rendered_content(self) -> str:
        raw_html = md.markdown(
            self.content or "",
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
        })

        allowed_attrs = {
            **bleach.sanitizer.ALLOWED_ATTRIBUTES,
            "a": ["href", "title", "target", "rel"],
            "img": ["src", "alt", "title"],
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
        return f"{self.post_id} - {self.order}"
