"""Mint and verify the short-lived playback tokens described by ADR-0008.

The Cloudflare Worker that fronts R2 is the consumer. To keep the two sides in
sync we expose two pure functions — :func:`mint_playback_token` and
:func:`verify_playback_token` — that read the signing parameters (secret,
algorithm, issuer, audience, TTL) from Django settings. The Worker is expected
to verify with the same secret, algorithm, issuer, and audience, so the
round-trip test in :mod:`tests.test_playback_tokens` doubles as a
specification.

Claims:

* ``sub`` — the Clerk user subject the token was minted for.
* ``gid`` — the game id the URL is scoped to.
* ``iat`` / ``exp`` — issued-at / expiry (UNIX seconds).
* ``iss`` / ``aud`` — bound to ``settings.PLAYBACK_TOKEN_ISSUER`` and
  ``settings.PLAYBACK_TOKEN_AUDIENCE`` so a token minted for one environment
  cannot be replayed against another.

The TTL is hard-capped at :data:`MAX_TTL_SECONDS` (15 minutes) so a
mis-configured environment can never issue a longer-lived URL than the
acceptance criteria allow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from django.conf import settings

# Hard ceiling on token lifetime. The AC pins this at 15 minutes; encoding it
# as a constant means an over-eager ``PLAYBACK_TOKEN_TTL_SECONDS`` env value
# cannot exceed it.
MAX_TTL_SECONDS = 15 * 60

# Default signing algorithm. HS256 keeps the Worker's verification cheap
# (single shared secret, no key fetch) which matches ADR-0008's "validate
# in-Worker, no external call" requirement.
DEFAULT_ALGORITHM = "HS256"
DEFAULT_ISSUER = "griddy-api"
DEFAULT_AUDIENCE = "griddy-video-worker"


class PlaybackTokenError(Exception):
    """Base class for any failure minting or verifying a playback token."""


class PlaybackTokenConfigError(PlaybackTokenError):
    """Raised when required signing settings are missing or invalid."""


class PlaybackTokenInvalid(PlaybackTokenError):
    """Raised when a token fails verification (expired, tampered, mis-scoped)."""


@dataclass(frozen=True)
class PlaybackTokenParams:
    """Snapshot of the signing parameters at mint time.

    Tests and the Worker stub both want one place to read the resolved
    config; pulling it through this dataclass also keeps
    :func:`mint_playback_token` itself easy to read.
    """

    secret: str
    algorithm: str
    issuer: str
    audience: str
    ttl_seconds: int


def _resolve_params(ttl_seconds: int | None = None) -> PlaybackTokenParams:
    """Read playback signing parameters from settings, applying the TTL cap."""
    secret = getattr(settings, "PLAYBACK_TOKEN_SECRET", None)
    if not secret:
        raise PlaybackTokenConfigError(
            "PLAYBACK_TOKEN_SECRET is not configured; cannot mint playback tokens."
        )

    algorithm = getattr(settings, "PLAYBACK_TOKEN_ALGORITHM", DEFAULT_ALGORITHM)
    issuer = getattr(settings, "PLAYBACK_TOKEN_ISSUER", DEFAULT_ISSUER)
    audience = getattr(settings, "PLAYBACK_TOKEN_AUDIENCE", DEFAULT_AUDIENCE)

    configured_ttl = ttl_seconds
    if configured_ttl is None:
        configured_ttl = getattr(
            settings, "PLAYBACK_TOKEN_TTL_SECONDS", MAX_TTL_SECONDS
        )
    if configured_ttl <= 0:
        raise PlaybackTokenConfigError(
            f"PLAYBACK_TOKEN_TTL_SECONDS must be positive (got {configured_ttl})."
        )
    # AC: TTL of 15 minutes or less. Cap silently rather than crash so a
    # caller passing a larger override still gets a valid (shorter) token.
    capped_ttl = min(configured_ttl, MAX_TTL_SECONDS)

    return PlaybackTokenParams(
        secret=secret,
        algorithm=algorithm,
        issuer=issuer,
        audience=audience,
        ttl_seconds=capped_ttl,
    )


@dataclass(frozen=True)
class MintedPlaybackToken:
    """Wraps the encoded JWT and the moment it expires.

    The API view needs both: the encoded form goes into the playback URL, the
    expiry feeds the ``expires_at`` field of the response.
    """

    token: str
    expires_at: datetime


def mint_playback_token(
    *,
    subject: str,
    game_id: int | str,
    ttl_seconds: int | None = None,
    now: datetime | None = None,
) -> MintedPlaybackToken:
    """Mint a short-lived playback token for ``subject`` and ``game_id``.

    ``now`` is overridable to make the call deterministic in tests; production
    callers should let it default to ``datetime.now(UTC)``.
    """
    params = _resolve_params(ttl_seconds)
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=params.ttl_seconds)

    payload: dict[str, Any] = {
        "sub": subject,
        "gid": str(game_id),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": params.issuer,
        "aud": params.audience,
    }
    token = jwt.encode(payload, params.secret, algorithm=params.algorithm)
    return MintedPlaybackToken(token=token, expires_at=expires_at)


def verify_playback_token(
    token: str,
    *,
    expected_game_id: int | str | None = None,
    expected_subject: str | None = None,
) -> dict[str, Any]:
    """Verify ``token`` against the configured signing parameters.

    On success returns the decoded claims dict. When ``expected_game_id`` or
    ``expected_subject`` are provided the corresponding claim must match
    exactly; this lets the Worker (or a test) assert that a token is scoped to
    the request it received.
    """
    params = _resolve_params()
    try:
        claims = jwt.decode(
            token,
            params.secret,
            algorithms=[params.algorithm],
            audience=params.audience,
            issuer=params.issuer,
        )
    except jwt.ExpiredSignatureError as exc:
        raise PlaybackTokenInvalid("playback token has expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise PlaybackTokenInvalid("playback token audience mismatch") from exc
    except jwt.InvalidIssuerError as exc:
        raise PlaybackTokenInvalid("playback token issuer mismatch") from exc
    except jwt.PyJWTError as exc:
        raise PlaybackTokenInvalid(f"playback token is invalid: {exc}") from exc

    if expected_game_id is not None and claims.get("gid") != str(expected_game_id):
        raise PlaybackTokenInvalid("playback token is not scoped to this game")
    if expected_subject is not None and claims.get("sub") != expected_subject:
        raise PlaybackTokenInvalid("playback token is not scoped to this user")
    return claims
