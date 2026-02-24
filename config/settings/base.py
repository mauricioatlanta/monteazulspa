from pathlib import Path
from decouple import config as env

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-secret-change-me")

# Producción: por defecto False
DEBUG = env("DJANGO_DEBUG", default=False, cast=bool)

# Hosts permitidos (incluye tu dominio real)
ALLOWED_HOSTS = [
    "monteazulspa.cl",
    "www.monteazulspa.cl",
    "127.0.0.1",
    "localhost",
]

# CSRF trusted origins (necesario para POST en dominios reales)
CSRF_TRUSTED_ORIGINS = env(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default="http://monteazulspa.cl,http://www.monteazulspa.cl,https://monteazulspa.cl,https://www.monteazulspa.cl"
).split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sitemaps",

    # Apps
    "apps.core.apps.CoreConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.customers.apps.CustomersConfig",
    "apps.catalog.apps.CatalogConfig",
    "apps.inventory.apps.InventoryConfig",
    "apps.cart.apps.CartConfig",
    "apps.orders.apps.OrdersConfig",
    "apps.payments.apps.PaymentsConfig",
    "apps.shipping.apps.ShippingConfig",
    "apps.audit.apps.AuditConfig",
    "apps.reports.apps.ReportsConfig",
    "apps.ops.apps.OpsConfig",
    "apps.reviews.apps.ReviewsConfig",
    "apps.blog.apps.BlogConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": env("DB_ENGINE", default="django.db.backends.sqlite3"),
        "NAME": env("DB_NAME", default=str(BASE_DIR / "db.sqlite3")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Transbank Webpay Plus (NUNCA hardcode; usar .env) ---
TBK_ENV = env("TBK_ENV", default="integration").strip().lower()
TBK_COMMERCE_CODE = env("TBK_COMMERCE_CODE", default="597055555532").strip()
TBK_API_KEY = env("TBK_API_KEY", default="").strip()
TBK_RETURN_URL = env(
    "TBK_RETURN_URL",
    default="https://monteazulspa.cl/carrito/webpay/retorno/",
).strip()
