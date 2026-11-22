"""SkillVar settings. All secrets and environment-specific values come from environment variables / .env."""
import os
from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(os.environ.get("SKILLVAR_ENV_FILE", BASE_DIR / ".env"))  # silently ignored if missing

DEBUG = env.bool("DEBUG", default=False)
SECRET_KEY = env("SECRET_KEY", default="")
if not DEBUG and (len(SECRET_KEY) < 32 or SECRET_KEY.startswith("change-me")):
    raise ImproperlyConfigured("With DEBUG off, set SECRET_KEY to a unique random value of at least 32 characters.")
if DEBUG and not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY is not set. Copy .env.example to .env and edit it.")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "testserver"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "axes",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "apps.accounts",
    "apps.skills",
    "apps.resumes",
    "apps.jobs",
    "apps.assessments",
    "apps.roadmaps",
    "apps.evidence",
    "apps.matching",
    "apps.dataops",
    "apps.web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "apps.web.context_processors.site_flags",
    ]},
}]

# --- Database: PostgreSQL is the intended database. DATABASE_URL is required. ---
try:
    DATABASES = {"default": env.db("DATABASE_URL")}
except environ.ImproperlyConfigured as exc:
    raise ImproperlyConfigured("DATABASE_URL is not set. See .env.example (PostgreSQL URL).") from exc
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CACHES = {"default": env.cache("CACHE_URL", default="dbcache://skillvar_cache")}

# --- Authentication ---
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",           # must be first: enforces login lockout
    "apps.accounts.backends.EmailOrUsernameBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"
SITE_ID = 1
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_RESET_ON_SUCCESS = True
AXES_ENABLED = env.bool("AXES_ENABLED", default=True)
AXES_LOCKOUT_TEMPLATE = "accounts/lockout.html"

# allauth is used ONLY for optional Google sign-in; local sign-up/login use SkillVar's own pages.
ACCOUNT_ADAPTER = "apps.accounts.adapters.ClosedLocalSignupAdapter"
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_METHODS = {"email", "username"}
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = False                  # login must start with a CSRF-protected POST
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False          # never auto-link a Google login to an existing local account
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")
SOCIALACCOUNT_PROVIDERS = {"google": {"SCOPE": ["profile", "email"], "AUTH_PARAMS": {"access_type": "online"}}}
if GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET:
    SOCIALACCOUNT_PROVIDERS["google"]["APP"] = {"client_id": GOOGLE_OAUTH_CLIENT_ID,
                                                "secret": GOOGLE_OAUTH_CLIENT_SECRET, "key": ""}

EMAIL_CONFIG = env.email("EMAIL_URL", default="consolemail://")
vars().update(EMAIL_CONFIG)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="SkillVar <noreply@localhost>")

# --- Static and private files ---
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_ROOT.mkdir(exist_ok=True)   # WhiteNoise warns if the folder is missing
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
_private = Path(env("PRIVATE_MEDIA_ROOT", default="private_media"))
PRIVATE_MEDIA_ROOT = _private if _private.is_absolute() else BASE_DIR / _private
RESUME_MAX_BYTES = env.int("RESUME_MAX_MB", default=5) * 1024 * 1024
RESUME_MAX_PAGES = 30
RESUME_MAX_TEXT_CHARS = 200_000
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024        # larger uploads stream to a temp file
DATA_UPLOAD_MAX_MEMORY_SIZE = 1 * 1024 * 1024        # non-file request bodies
JOB_TEXT_MAX_CHARS = 20_000

# --- Product heuristics (documented in docs/MATCHING.md). These are starting values, not constants of nature. ---
MATCH_WEIGHTS = {"required": 0.6, "preferred": 0.2, "experience": 0.2}
MATCH_CREDITS = {"claimed": 0.2, "contextual": 0.5}     # credit for non-assessed evidence tiers
UNDECIDED_ASSESSMENT_CAP = 0.5                          # credit ceiling while assessment evidence is still thin
FORMULA_VERSION = "2026.1"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"user": "600/hour"},
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True

# --- Security headers / cookies ---
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
    if env.bool("BEHIND_PROXY", default=False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {"skillvar": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}
