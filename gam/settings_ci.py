"""
Minimal Django settings for CI.

Uses SQLite so CI doesn't require a PostgreSQL service.
"""

from gam.settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable debug toolbar in CI
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "debug_toolbar"]  # noqa: F405
MIDDLEWARE = [m for m in MIDDLEWARE if "debug_toolbar" not in m]  # noqa: F405

# Disable throttling in CI to prevent rate-limit interference with tests.
# Permissions remain active; most existing tests use AllowAny-equivalent
# unauthenticated Django Client. The TGF-311 cross-cutting tests explicitly
# test auth/permission behavior by overriding settings per test.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
    # Allow unauthenticated writes in CI so existing tests pass.
    # Cross-cutting auth tests override this per-test.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}
