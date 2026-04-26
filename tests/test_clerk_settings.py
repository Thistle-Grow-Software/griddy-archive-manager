"""
Tests for the Clerk settings wiring (TGF-315).

These cover the bridge from Clerk-named env vars to the IdP-agnostic Django
settings consumed by :class:`gam.auth.jwt.JWKSAuthentication`, plus the DRF
``DEFAULT_AUTHENTICATION_CLASSES`` registration. The auth-class behavior
itself is covered by ``test_jwks_auth.py``.
"""

from __future__ import annotations

import importlib

from django.conf import settings


def test_jwks_auth_in_default_authentication_classes():
    """JWKSAuthentication must be wired as a default DRF auth class."""
    auth_classes = settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
    assert "gam.auth.jwt.JWKSAuthentication" in auth_classes


def test_clerk_settings_attributes_exist():
    """Settings module must expose every Clerk-bridged value."""
    for attr in (
        "JWKS_URL",
        "JWT_AUDIENCE",
        "JWT_ISSUER",
        "JWT_AUTHORIZED_PARTIES",
        "CLERK_SECRET_KEY",
    ):
        assert hasattr(settings, attr), f"settings.{attr} is missing"


def test_authorized_parties_defaults_to_empty_list_when_unset(monkeypatch):
    """Unset env var → empty list (no enforcement)."""
    monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)
    import gam.settings as gam_settings

    importlib.reload(gam_settings)
    assert gam_settings.JWT_AUTHORIZED_PARTIES == []


def test_authorized_parties_parses_comma_separated_values(monkeypatch):
    monkeypatch.setenv(
        "CLERK_AUTHORIZED_PARTIES",
        "http://localhost:3000,https://portal.griddy.test",
    )
    import gam.settings as gam_settings

    importlib.reload(gam_settings)
    assert gam_settings.JWT_AUTHORIZED_PARTIES == [
        "http://localhost:3000",
        "https://portal.griddy.test",
    ]


def test_authorized_parties_strips_whitespace_and_skips_empties(monkeypatch):
    monkeypatch.setenv(
        "CLERK_AUTHORIZED_PARTIES",
        " http://localhost:3000 , ,https://portal.griddy.test ",
    )
    import gam.settings as gam_settings

    importlib.reload(gam_settings)
    assert gam_settings.JWT_AUTHORIZED_PARTIES == [
        "http://localhost:3000",
        "https://portal.griddy.test",
    ]


def test_clerk_env_vars_drive_jwks_settings(monkeypatch):
    """Each generic JWT setting reads from its CLERK_* env var counterpart."""
    monkeypatch.setenv(
        "CLERK_JWKS_URL", "https://example.clerk.accounts.dev/.well-known/jwks.json"
    )
    monkeypatch.setenv("CLERK_ISSUER", "https://example.clerk.accounts.dev")
    monkeypatch.setenv("CLERK_AUDIENCE", "https://api.griddy.test")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_dummy")
    import gam.settings as gam_settings

    importlib.reload(gam_settings)
    assert (
        gam_settings.JWKS_URL
        == "https://example.clerk.accounts.dev/.well-known/jwks.json"
    )
    assert gam_settings.JWT_ISSUER == "https://example.clerk.accounts.dev"
    assert gam_settings.JWT_AUDIENCE == "https://api.griddy.test"
    assert gam_settings.CLERK_SECRET_KEY == "sk_test_dummy"


def test_settings_reload_with_no_clerk_env_yields_none(monkeypatch):
    """Reloading with no Clerk env vars yields ``None`` values, not stale ones."""
    for var in (
        "CLERK_JWKS_URL",
        "CLERK_ISSUER",
        "CLERK_AUDIENCE",
        "CLERK_AUTHORIZED_PARTIES",
        "CLERK_SECRET_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    import gam.settings as gam_settings

    importlib.reload(gam_settings)
    assert gam_settings.JWKS_URL is None
    assert gam_settings.JWT_ISSUER is None
    assert gam_settings.JWT_AUDIENCE is None
    assert gam_settings.CLERK_SECRET_KEY is None
    assert gam_settings.JWT_AUTHORIZED_PARTIES == []
