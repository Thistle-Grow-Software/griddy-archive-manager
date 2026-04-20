"""Tests to verify the archive/api/ package structure meets TGF-287 acceptance criteria."""

import importlib
from pathlib import Path

from rest_framework.pagination import CursorPagination
from rest_framework.routers import DefaultRouter

API_DIR = Path(__file__).resolve().parents[1] / "archive" / "api"


# --- Package existence ---


def test_api_init_exists():
    """archive/api/__init__.py must exist."""
    assert (API_DIR / "__init__.py").exists()


def test_serializers_init_exists():
    """archive/api/serializers/__init__.py must exist."""
    assert (API_DIR / "serializers" / "__init__.py").exists()


def test_viewsets_init_exists():
    """archive/api/viewsets/__init__.py must exist."""
    assert (API_DIR / "viewsets" / "__init__.py").exists()


def test_filters_module_exists():
    """archive/api/filters.py must exist."""
    assert (API_DIR / "filters.py").exists()


# --- Router ---


def test_router_module_exists():
    """archive/api/router.py must exist."""
    assert (API_DIR / "router.py").exists()


def test_router_is_default_router():
    """router.py must export a DefaultRouter instance."""
    mod = importlib.import_module("archive.api.router")
    assert isinstance(mod.router, DefaultRouter)


def test_router_urlpatterns_includes_router_urls():
    """router.py must define urlpatterns that include router.urls."""
    mod = importlib.import_module("archive.api.router")
    assert hasattr(mod, "urlpatterns")
    # urlpatterns includes all router URLs plus any nested URL patterns
    for url in mod.router.urls:
        assert url in mod.urlpatterns


# --- Pagination ---


def test_pagination_module_exists():
    """archive/api/pagination.py must exist."""
    assert (API_DIR / "pagination.py").exists()


def test_default_cursor_pagination_exists():
    """DefaultCursorPagination must be defined and extend CursorPagination."""
    mod = importlib.import_module("archive.api.pagination")
    assert hasattr(mod, "DefaultCursorPagination")
    assert issubclass(mod.DefaultCursorPagination, CursorPagination)


def test_default_cursor_pagination_page_size():
    """DefaultCursorPagination must have page_size=50."""
    mod = importlib.import_module("archive.api.pagination")
    assert mod.DefaultCursorPagination.page_size == 50


def test_game_pagination_exists():
    """GamePagination must be defined and extend CursorPagination."""
    mod = importlib.import_module("archive.api.pagination")
    assert hasattr(mod, "GamePagination")
    assert issubclass(mod.GamePagination, CursorPagination)


def test_play_pagination_exists():
    """PlayPagination must be defined and extend CursorPagination."""
    mod = importlib.import_module("archive.api.pagination")
    assert hasattr(mod, "PlayPagination")
    assert issubclass(mod.PlayPagination, CursorPagination)


# --- Importability ---


def test_api_package_importable():
    """archive.api must be importable."""
    mod = importlib.import_module("archive.api")
    assert mod is not None


def test_serializers_package_importable():
    """archive.api.serializers must be importable."""
    mod = importlib.import_module("archive.api.serializers")
    assert mod is not None


def test_viewsets_package_importable():
    """archive.api.viewsets must be importable."""
    mod = importlib.import_module("archive.api.viewsets")
    assert mod is not None
