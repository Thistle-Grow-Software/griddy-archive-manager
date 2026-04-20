"""Tests to verify Django REST Framework configuration meets TGF-286 acceptance criteria."""

from django.conf import settings


def test_rest_framework_in_installed_apps():
    """rest_framework must be in INSTALLED_APPS."""
    assert "rest_framework" in settings.INSTALLED_APPS


def test_django_filters_in_installed_apps():
    """django_filters must be in INSTALLED_APPS."""
    assert "django_filters" in settings.INSTALLED_APPS


def test_rest_framework_dict_exists():
    """REST_FRAMEWORK settings dict must be defined."""
    assert hasattr(settings, "REST_FRAMEWORK")
    assert isinstance(settings.REST_FRAMEWORK, dict)


def test_pagination_class_is_cursor():
    """Default pagination must be CursorPagination."""
    assert (
        settings.REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"]
        == "rest_framework.pagination.CursorPagination"
    )


def test_page_size_is_50():
    """PAGE_SIZE must be 50."""
    assert settings.REST_FRAMEWORK["PAGE_SIZE"] == 50


def test_filter_backends_include_django_filter():
    """DjangoFilterBackend must be in DEFAULT_FILTER_BACKENDS."""
    backends = settings.REST_FRAMEWORK["DEFAULT_FILTER_BACKENDS"]
    assert "django_filters.rest_framework.DjangoFilterBackend" in backends


def test_filter_backends_include_search_filter():
    """SearchFilter must be in DEFAULT_FILTER_BACKENDS."""
    backends = settings.REST_FRAMEWORK["DEFAULT_FILTER_BACKENDS"]
    assert "rest_framework.filters.SearchFilter" in backends


def test_filter_backends_include_ordering_filter():
    """OrderingFilter must be in DEFAULT_FILTER_BACKENDS."""
    backends = settings.REST_FRAMEWORK["DEFAULT_FILTER_BACKENDS"]
    assert "rest_framework.filters.OrderingFilter" in backends


def test_renderer_classes_include_json():
    """JSONRenderer must be in DEFAULT_RENDERER_CLASSES."""
    renderers = settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"]
    assert "rest_framework.renderers.JSONRenderer" in renderers


def test_renderer_classes_include_browsable_api():
    """BrowsableAPIRenderer must be in DEFAULT_RENDERER_CLASSES."""
    renderers = settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"]
    assert "rest_framework.renderers.BrowsableAPIRenderer" in renderers
