"""
API key authentication for SDK / machine-to-machine requests (TGF-318).

Companion to :class:`gam.auth.jwt.JWKSAuthentication`. Both classes can sit
in ``DEFAULT_AUTHENTICATION_CLASSES`` simultaneously; each returns ``None``
for headers it does not recognize so DRF falls through to the next class.

Token format: ``grd_{live|test}_{48 hex chars}``. The plaintext key is
shown to the operator exactly once at issuance and never persisted — only
its SHA-256 hash and a short ``key_prefix`` (for indexed lookup) live in
the database. SHA-256 is appropriate here because keys are high-entropy
random; argon2/bcrypt would only be useful for low-entropy passwords.

Authentication:

1. Parse ``Authorization: Bearer <token>``. If the token does not start
   with ``grd_``, return ``None`` (let JWT auth handle it).
2. Validate the token shape with a strict regex.
3. Look up candidate keys by ``key_prefix`` (single indexed query).
4. For each candidate, compare the SHA-256 of the presented token against
   the stored ``key_hash`` using ``hmac.compare_digest`` (constant time).
5. Reject revoked / expired keys with ``AuthenticationFailed``.
6. Return ``(account, api_key)`` so views can read scopes off the auth
   object and identify the owner.

The ``last_used_at`` timestamp is updated via ``transaction.on_commit``
with a per-key throttle so we do not amplify request-rate writes 1:1.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework import authentication, exceptions

from gam.accounts.models import APIKey, APIKeyEnvironment, ClerkAccount

# Total key length is ``len(scheme_prefix) + 48`` hex chars (e.g.
# ``grd_live_<48 hex>``). 48 hex = 192 bits of entropy — well above the
# 128-bit floor that makes brute force infeasible.
_SECRET_BYTES = 24  # secrets.token_hex(24) → 48 chars
_KEY_RE = re.compile(r"^grd_(live|test)_([0-9a-f]{48})$")
_PREFIX_HINT_LENGTH = 8

# Update last_used_at at most once per this many seconds per key.
LAST_USED_THROTTLE_SECONDS = 60


def _hash_token(token: str) -> str:
    """Return the hex SHA-256 of ``token`` for storage / comparison."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _build_prefix(environment: str, secret: str) -> str:
    return f"grd_{environment}_{secret[:_PREFIX_HINT_LENGTH]}"


def generate_api_key(
    account: ClerkAccount,
    *,
    name: str,
    environment: str = APIKeyEnvironment.LIVE,
    scopes: list[str] | None = None,
    expires_at: Any = None,
) -> tuple[APIKey, str]:
    """Mint a new API key, persist its hash, and return ``(api_key, plaintext)``.

    The plaintext token is the **only** copy — callers must show it to the
    operator immediately and discard it. Subsequent reads of the ``APIKey``
    row will not be able to recover the token.
    """
    if environment not in APIKeyEnvironment.values:
        raise ValueError(
            f"environment must be one of {APIKeyEnvironment.values!r}, "
            f"got {environment!r}"
        )
    secret = secrets.token_hex(_SECRET_BYTES)
    plaintext = f"grd_{environment}_{secret}"
    api_key = APIKey.objects.create(
        account=account,
        name=name,
        environment=environment,
        key_prefix=_build_prefix(environment, secret),
        key_hash=_hash_token(plaintext),
        scopes=list(scopes or []),
        expires_at=expires_at,
    )
    return api_key, plaintext


class APIKeyAuthentication(authentication.BaseAuthentication):
    """DRF authentication backend for ``Bearer grd_*`` tokens."""

    keyword = "Bearer"

    def authenticate(self, request: Any) -> tuple[ClerkAccount, APIKey] | None:
        token = self._extract_bearer_token(request)
        if token is None or not token.startswith("grd_"):
            return None

        match = _KEY_RE.match(token)
        if not match:
            raise exceptions.AuthenticationFailed("Malformed API key.")
        environment, secret = match.group(1), match.group(2)
        prefix = _build_prefix(environment, secret)
        token_hash = _hash_token(token)

        candidates = APIKey.objects.select_related("account").filter(key_prefix=prefix)
        api_key = self._match_candidate(candidates, token_hash)
        if api_key is None:
            raise exceptions.AuthenticationFailed("Invalid API key.")

        self._validate_lifecycle(api_key)
        _schedule_last_used_update(api_key.id)
        return (api_key.account, api_key)

    def authenticate_header(self, request: Any) -> str:
        return self.keyword

    def _extract_bearer_token(self, request: Any) -> str | None:
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header:
            return None
        parts = header.split()
        if parts[0] != self.keyword:
            return None
        if len(parts) != 2:
            return None
        return parts[1]

    @staticmethod
    def _match_candidate(candidates, token_hash: str) -> APIKey | None:
        # Iterate every candidate even after a hit so timing observations
        # cannot reveal whether the prefix matched 1, 2, or N rows.
        match: APIKey | None = None
        for candidate in candidates:
            if hmac.compare_digest(candidate.key_hash, token_hash):
                match = candidate
        return match

    @staticmethod
    def _validate_lifecycle(api_key: APIKey) -> None:
        if api_key.is_revoked:
            raise exceptions.AuthenticationFailed("API key has been revoked.")
        if api_key.is_expired:
            raise exceptions.AuthenticationFailed("API key has expired.")


def _schedule_last_used_update(api_key_id: int) -> None:
    """Defer a throttled ``last_used_at`` UPDATE until after the response.

    Wrapping the write in :func:`transaction.on_commit` keeps it off the
    request critical path. The throttle predicate (``last_used_at`` is
    null OR older than the threshold) collapses bursts of requests from
    the same key into at most one write per ``LAST_USED_THROTTLE_SECONDS``
    window, without needing Celery / Redis.
    """

    def update() -> None:
        threshold = timezone.now() - timedelta(seconds=LAST_USED_THROTTLE_SECONDS)
        APIKey.objects.filter(pk=api_key_id).filter(
            models_q_last_used_stale(threshold)
        ).update(last_used_at=timezone.now())

    # ``on_commit`` runs the callable immediately if there's no open
    # transaction, otherwise queues it for the post-commit hook.
    transaction.on_commit(update)


def models_q_last_used_stale(threshold) -> Any:
    """Return a Q expression matching keys whose last_used_at is stale.

    Defined as a helper to keep the import surface in the auth module
    minimal and to make the predicate independently testable.
    """
    from django.db.models import Q

    return Q(last_used_at__isnull=True) | Q(last_used_at__lt=threshold)
