import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in {"1", "true", "yes"}
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ValueError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is disabled.")
    SECRET_KEY = "local-only-unsafe-development-key-change-before-deployment"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173" if DEBUG else "",
    ).split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "core",
    "organizations",
    "customers",
    "products",
    "inventory",
    "sales",
    "audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.PlatformOwnerAdminMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
            BASE_DIR.parent / "frontend" / "dist",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "core.context_processors.platform_dashboard",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

database_url = os.environ.get("DATABASE_URL", "").strip()
if database_url:
    parsed_database_url = urlparse(database_url)
    if parsed_database_url.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must use the postgres:// or postgresql:// scheme.")
    database_options = parse_qs(parsed_database_url.query)
    database_sslmode = database_options.get(
        "sslmode",
        ["require" if not DEBUG else "prefer"],
    )[0]
    if not DEBUG and database_sslmode == "disable":
        raise ValueError("PostgreSQL SSL must not be disabled in production.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed_database_url.path.lstrip("/")),
            "USER": unquote(parsed_database_url.username or ""),
            "PASSWORD": unquote(parsed_database_url.password or ""),
            "HOST": parsed_database_url.hostname or "",
            "PORT": parsed_database_url.port or "",
            "CONN_MAX_AGE": 60,
            "OPTIONS": {
                "sslmode": database_sslmode,
            },
        }
    }
else:
    if not DEBUG:
        raise ValueError("DATABASE_URL must point to PostgreSQL when DJANGO_DEBUG is disabled.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ar"
TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"
STATICFILES_DIRS = [FRONTEND_DIST_DIR] if FRONTEND_DIST_DIR.exists() else []
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/hour",
        "registration": "5/hour",
        "password_reset": "5/hour",
        "email_verification": "5/hour",
    },
}

PUBLIC_APP_URL = os.environ.get(
    "PUBLIC_APP_URL",
    "http://localhost:5173" if DEBUG else "",
).rstrip("/")
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("DJANGO_EMAIL_USE_TLS", "True").lower() in {
    "1",
    "true",
    "yes",
}
EMAIL_USE_SSL = os.environ.get("DJANGO_EMAIL_USE_SSL", "False").lower() in {
    "1",
    "true",
    "yes",
}
EMAIL_TIMEOUT = int(os.environ.get("DJANGO_EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.environ.get(
    "DJANGO_DEFAULT_FROM_EMAIL",
    "no-reply@nasaq.local" if DEBUG else "",
)

if not DEBUG:
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ValueError("Set exact DJANGO_ALLOWED_HOSTS values in production.")
    if not CSRF_TRUSTED_ORIGINS:
        raise ValueError("Set HTTPS DJANGO_CSRF_TRUSTED_ORIGINS values in production.")
    if EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
        raise ValueError("Production must use Django's SMTP email backend.")
    required_production_settings = {
        "PUBLIC_APP_URL": PUBLIC_APP_URL,
        "DJANGO_EMAIL_HOST": EMAIL_HOST,
        "DJANGO_DEFAULT_FROM_EMAIL": DEFAULT_FROM_EMAIL,
    }
    missing_production_settings = [
        name for name, value in required_production_settings.items() if not value
    ]
    if missing_production_settings:
        raise ValueError(
            "Production settings must be configured: "
            + ", ".join(missing_production_settings)
        )
    if urlparse(PUBLIC_APP_URL).scheme != "https":
        raise ValueError("PUBLIC_APP_URL must use HTTPS when DJANGO_DEBUG is disabled.")
    if EMAIL_USE_TLS and EMAIL_USE_SSL:
        raise ValueError("Use either DJANGO_EMAIL_USE_TLS or DJANGO_EMAIL_USE_SSL, not both.")
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "django_cache",
            "TIMEOUT": 300,
        }
    }
    SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
    SESSION_SAVE_EVERY_REQUEST = False
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    SECURE_CONTENT_TYPE_NOSNIFF = True

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    if os.environ.get("DJANGO_BEHIND_TRUSTED_HTTPS_PROXY", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
