import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# --- .env 자동 로드 ---
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv(BASE_DIR / ".env")
except Exception:
    # python-dotenv 미설치/파일 없음이면 그냥 패스
    pass


def env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def env_list(name: str, default=None):
    if default is None:
        default = []
    val = os.environ.get(name)
    if not val:
        return default
    return [x.strip() for x in val.split(",") if x.strip()]


# 개발 편의 기본값
DEBUG = env_bool("DEBUG", True)

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ["127.0.0.1", "localhost"])

# (필요시)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", False)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Cloudinary 패키지는 설치돼 있어도 문제 없음
    "cloudinary_storage",
    "cloudinary",

    "apps.blog.apps.BlogConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if DEBUG:
    WHITENOISE_AUTOREFRESH = True
    WHITENOISE_USE_FINDERS = True


def has_cloudinary_credentials() -> bool:
    if os.environ.get("CLOUDINARY_URL"):
        return True
    if (
        os.environ.get("CLOUDINARY_CLOUD_NAME")
        and os.environ.get("CLOUDINARY_API_KEY")
        and os.environ.get("CLOUDINARY_API_SECRET")
    ):
        return True
    if os.environ.get("CLOUD_NAME") and os.environ.get("API_KEY") and os.environ.get("API_SECRET"):
        return True
    return False


USE_CLOUDINARY = env_bool("USE_CLOUDINARY", False) and has_cloudinary_credentials()

# cloudinary_storage가 기대하는 설정(환경변수에서 읽어 안전)
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME") or os.environ.get("CLOUD_NAME") or "",
    "API_KEY": os.environ.get("CLOUDINARY_API_KEY") or os.environ.get("API_KEY") or "",
    "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET") or os.environ.get("API_SECRET") or "",
}

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"
        if USE_CLOUDINARY
        else "django.core.files.storage.FileSystemStorage",
        # FileSystemStorage일 때만 의미 있음
        "OPTIONS": {"location": str(MEDIA_ROOT)} if not USE_CLOUDINARY else {},
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
