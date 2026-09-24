import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "local-development-only-change-me")
DEBUG = os.environ.get("DEBUG", "True").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [item.strip() for item in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",") if item.strip()]
CSRF_TRUSTED_ORIGINS = [item.strip() for item in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if item.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "collection",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "collection.middleware.ConsentEnforcementMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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
ASGI_APPLICATION = "config.asgi.application"

DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").lower()
if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "data_collection"),
            "USER": os.environ.get("DB_USER", ""),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / os.environ.get("DB_NAME", "data_collection.sqlite3"),
        }
    }

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

def first_env(*names, default=""):
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default


FACE_EXTRACT_URL = first_env("FACE_EXTRACT_URL")
FACE_EXTRACT_SESSION_VECTOR_URL_TEMPLATE = first_env("FACE_EXTRACT_SESSION_VECTOR_URL_TEMPLATE")
FACE_SCORE_URL = first_env("FACE_SCORE_URL")
FACE_EXTRACT_API_KEY = first_env("FACE_VIDEO_FEATURE_EXTRACTION_API_KEY", "FACE_EXTRACT_API_KEY", "FACE_API_KEY")
FACE_SCORE_API_KEY = first_env("FACE_VIDEO_FEATURE_TO_MH_API_KEY", "FACE_SCORE_API_KEY", "FACE_API_KEY")
FACE_API_KEY = FACE_EXTRACT_API_KEY
TEXT_EXTRACT_URL = first_env("TEXT_EXTRACT_URL")
TEXT_SCORE_URL = first_env("TEXT_SCORE_URL")
TEXT_EXTRACT_API_KEY = first_env("TEXT_PARAMETER_EXTRACT_API_KEY", "TEXT_EXTRACT_API_KEY", "TEXT_API_KEY")
TEXT_SCORE_API_KEY = first_env("TEXT_ANALYSIS_API_KEY", "TEXT_SCORE_API_KEY", "TEXT_API_KEY")
TEXT_API_KEY = TEXT_EXTRACT_API_KEY
SARVAM_API_KEY = first_env("SARVAM_API_KEY")
SARVAM_STT_MODEL = os.environ.get("SARVAM_STT_MODEL", "saaras:v3")
VOICE_EXTRACT_URL = first_env("VOICE_EXTRACT_URL")
VOICE_PCA_URL = first_env("VOICE_PCA_URL")
VOICE_SCORE_URL = first_env("VOICE_SCORE_URL")
VOICE_EXTRACT_API_KEY = first_env("VOICE_FEATURE_EXTRACT_API_KEY", "VOICE_EXTRACT_API_KEY", "VOICE_API_KEY")
VOICE_PCA_API_KEY = first_env("VOICE_PCA_API_KEY", "VOICE_API_KEY")
VOICE_SCORE_API_KEY = first_env("VOICE_FEATURE_TO_MH", "VOICE_FEATURE_TO_MH_API_KEY", "VOICE_SCORE_API_KEY", "VOICE_API_KEY")
VOICE_API_KEY = VOICE_EXTRACT_API_KEY
FUSION_SCORE_URL = first_env("FUSION_SCORE_URL")
FUSION_API_KEY = first_env("FUSION_API_KEY", "MODEL_API_KEY")
