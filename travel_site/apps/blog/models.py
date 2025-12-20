from django.db import models
from django.utils import timezone
import markdown as md
import bleach

class Country(models.Model):
    name = models.CharField(max_length=100)          # 표시용 국가명 (예: Japan)
    slug = models.SlugField(unique=True)             # URL/조회용 (예: japan)
    short_description = models.CharField(max_length=300, blank=True)

    # (선택) 국기/대표 이미지: 나중에 S3/Cloudinary 붙이면 그대로 사용 가능
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
        """
        content(마크다운)을 HTML로 변환하고, 허용 태그/속성만 남기도록 sanitize.
        """
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

        # 링크 보안 처리(새 탭 열기 같은 건 템플릿/프론트에서 컨트롤해도 OK)
        cleaned = cleaned.replace("<a ", '<a rel="nofollow noopener" target="_blank" ')
        return cleaned

# apps/blog/models.py
from django.db import models

class PostImage(models.Model):
    post = models.ForeignKey(
        "Post",
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="post_images/")
    caption = models.CharField(max_length=200, blank=True)

    # ✅ 갤러리/관리자에서 순서 제어용
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]  # ✅ 기본 정렬

    def __str__(self):
        return f"{self.post_id} - {self.order}"

