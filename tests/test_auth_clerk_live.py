"""
Live smoke test against the real Clerk dev instance (TGF-319).

Skipped by default. Enable by setting ``CLERK_LIVE_SMOKE=1`` and the four
required env vars listed below. Intended for a nightly CI job, not the
per-PR pytest run — it makes outbound calls to Clerk's Backend API and
depends on the dev instance staying configured.

Required environment variables when ``CLERK_LIVE_SMOKE=1``:

* ``CLERK_LIVE_SECRET_KEY``     — Clerk Backend API secret (sk_test_…).
* ``CLERK_LIVE_USER_ID``        — A pre-created user_… ID to mint a token for.
* ``CLERK_LIVE_JWKS_URL``       — JWKS endpoint of the same Clerk instance.
* ``CLERK_LIVE_ISSUER``         — ``iss`` claim Clerk emits.
* ``CLERK_LIVE_AUDIENCE``       — ``aud`` claim Clerk emits (or session
  audience if you customized it).

The test mints a session token via the Backend API, points Django at the
matching JWKS URL, and confirms a representative endpoint returns 200.
A failure here means either the env is misconfigured (likely) or Clerk
changed something we depend on (rare but worth catching).
"""

from __future__ import annotations

import os

import pytest
import requests
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

CLERK_API_BASE = "https://api.clerk.com/v1"

pytestmark = [pytest.mark.django_db, pytest.mark.smoke]


def _required_env() -> dict[str, str] | None:
    keys = (
        "CLERK_LIVE_SECRET_KEY",
        "CLERK_LIVE_USER_ID",
        "CLERK_LIVE_JWKS_URL",
        "CLERK_LIVE_ISSUER",
        "CLERK_LIVE_AUDIENCE",
    )
    values = {k: os.getenv(k, "") for k in keys}
    if any(not v for v in values.values()):
        return None
    return values


@pytest.fixture
def live_env() -> dict[str, str]:
    if os.getenv("CLERK_LIVE_SMOKE") != "1":
        pytest.skip("CLERK_LIVE_SMOKE=1 not set; skipping live Clerk smoke test.")
    env = _required_env()
    if env is None:
        pytest.skip("Required CLERK_LIVE_* env vars not configured.")
    return env


def _mint_session_token(secret_key: str, user_id: str) -> str:
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }
    session = requests.post(
        f"{CLERK_API_BASE}/sessions",
        headers=headers,
        json={"user_id": user_id},
        timeout=10,
    )
    session.raise_for_status()
    session_id = session.json()["id"]

    token = requests.post(
        f"{CLERK_API_BASE}/sessions/{session_id}/tokens",
        headers=headers,
        timeout=10,
    )
    token.raise_for_status()
    return token.json()["jwt"]


def test_live_clerk_token_authorizes_against_local_django(live_env):
    """Mint a token from the live Clerk dev instance, hit a real endpoint."""
    token = _mint_session_token(
        live_env["CLERK_LIVE_SECRET_KEY"],
        live_env["CLERK_LIVE_USER_ID"],
    )

    from gam.auth.jwt import _get_jwks_client

    _get_jwks_client.cache_clear()
    with override_settings(
        JWKS_URL=live_env["CLERK_LIVE_JWKS_URL"],
        JWT_ISSUER=live_env["CLERK_LIVE_ISSUER"],
        JWT_AUDIENCE=live_env["CLERK_LIVE_AUDIENCE"],
        JWT_AUTHORIZED_PARTIES=[],
    ):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = client.get(reverse("league-list"))

    # 200 if the configured Clerk user has catalog:read; 403 if not. Either
    # outcome proves the JWT validated against the JWKS (a 401 would mean
    # the dev instance JWKS / issuer / audience drifted from what we set).
    assert response.status_code in {200, 403}, (
        f"Unexpected {response.status_code} from live Clerk smoke test; "
        "JWKS / issuer / audience likely drifted."
    )
