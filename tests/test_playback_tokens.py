"""Unit tests for :mod:`gam.playback.tokens` (TGF-360).

The Worker that fronts R2 verifies these tokens, so the mint / verify
round-trip here doubles as the inter-component contract test required by the
ticket's AC.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from django.test import override_settings

from gam.playback.tokens import (
    DEFAULT_ALGORITHM,
    DEFAULT_AUDIENCE,
    DEFAULT_ISSUER,
    MAX_TTL_SECONDS,
    PlaybackTokenConfigError,
    PlaybackTokenInvalid,
    mint_playback_token,
    verify_playback_token,
)

SHARED_SECRET = "test-playback-secret-with-at-least-32-bytes"


@pytest.fixture
def configured_signing():
    """Pin every signing parameter so tests don't depend on env defaults."""
    with override_settings(
        PLAYBACK_TOKEN_SECRET=SHARED_SECRET,
        PLAYBACK_TOKEN_ALGORITHM=DEFAULT_ALGORITHM,
        PLAYBACK_TOKEN_ISSUER=DEFAULT_ISSUER,
        PLAYBACK_TOKEN_AUDIENCE=DEFAULT_AUDIENCE,
        PLAYBACK_TOKEN_TTL_SECONDS=900,
    ):
        yield


@pytest.mark.usefixtures("configured_signing")
class TestMintAndVerifyRoundTrip:
    def test_round_trip_returns_claims(self):
        minted = mint_playback_token(subject="user_42", game_id=7)
        claims = verify_playback_token(
            minted.token, expected_game_id=7, expected_subject="user_42"
        )
        assert claims["sub"] == "user_42"
        assert claims["gid"] == "7"
        assert claims["iss"] == DEFAULT_ISSUER
        assert claims["aud"] == DEFAULT_AUDIENCE

    def test_expires_at_matches_iat_plus_ttl(self):
        now = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
        minted = mint_playback_token(subject="user_42", game_id=7, now=now)
        assert minted.expires_at == now + timedelta(seconds=900)

    def test_worker_can_independently_verify_same_secret(self):
        """The Worker uses raw ``jwt.decode``; mirror that here."""
        minted = mint_playback_token(subject="user_42", game_id=7)
        claims = jwt.decode(
            minted.token,
            SHARED_SECRET,
            algorithms=[DEFAULT_ALGORITHM],
            audience=DEFAULT_AUDIENCE,
            issuer=DEFAULT_ISSUER,
        )
        assert claims["gid"] == "7"
        assert claims["sub"] == "user_42"


@pytest.mark.usefixtures("configured_signing")
class TestTokenScoping:
    def test_wrong_game_id_rejected(self):
        minted = mint_playback_token(subject="user_42", game_id=7)
        with pytest.raises(PlaybackTokenInvalid, match="game"):
            verify_playback_token(minted.token, expected_game_id=999)

    def test_wrong_subject_rejected(self):
        minted = mint_playback_token(subject="user_42", game_id=7)
        with pytest.raises(PlaybackTokenInvalid, match="user"):
            verify_playback_token(minted.token, expected_subject="user_other")

    def test_token_signed_with_other_secret_rejected(self):
        foreign = jwt.encode(
            {
                "sub": "user_42",
                "gid": "7",
                "iss": DEFAULT_ISSUER,
                "aud": DEFAULT_AUDIENCE,
                "iat": int(datetime.now(UTC).timestamp()),
                "exp": int((datetime.now(UTC) + timedelta(seconds=60)).timestamp()),
            },
            "a-different-secret-also-with-32-plus-bytes",
            algorithm=DEFAULT_ALGORITHM,
        )
        with pytest.raises(PlaybackTokenInvalid):
            verify_playback_token(foreign)

    def test_expired_token_rejected(self):
        past = datetime.now(UTC) - timedelta(seconds=2 * MAX_TTL_SECONDS)
        minted = mint_playback_token(
            subject="user_42",
            game_id=7,
            ttl_seconds=1,
            now=past,
        )
        with pytest.raises(PlaybackTokenInvalid, match="expired"):
            verify_playback_token(minted.token)


class TestTTLCap:
    def test_ttl_is_capped_at_max(self):
        with override_settings(
            PLAYBACK_TOKEN_SECRET=SHARED_SECRET,
            PLAYBACK_TOKEN_TTL_SECONDS=MAX_TTL_SECONDS * 4,
        ):
            now = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
            minted = mint_playback_token(subject="user_42", game_id=7, now=now)
        # The cap is the 15-minute AC ceiling — anything larger gets clamped
        # silently so a misconfigured env can't issue longer-lived URLs.
        assert minted.expires_at - now == timedelta(seconds=MAX_TTL_SECONDS)

    def test_explicit_ttl_override_below_cap_is_used(self):
        with override_settings(PLAYBACK_TOKEN_SECRET=SHARED_SECRET):
            now = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
            minted = mint_playback_token(
                subject="user_42", game_id=7, ttl_seconds=120, now=now
            )
        assert minted.expires_at - now == timedelta(seconds=120)


class TestConfigErrors:
    def test_missing_secret_raises_config_error(self):
        with (
            override_settings(PLAYBACK_TOKEN_SECRET=""),
            pytest.raises(PlaybackTokenConfigError, match="PLAYBACK_TOKEN_SECRET"),
        ):
            mint_playback_token(subject="user_42", game_id=7)

    def test_non_positive_ttl_raises_config_error(self):
        with (
            override_settings(
                PLAYBACK_TOKEN_SECRET=SHARED_SECRET,
                PLAYBACK_TOKEN_TTL_SECONDS=0,
            ),
            pytest.raises(PlaybackTokenConfigError, match="positive"),
        ):
            mint_playback_token(subject="user_42", game_id=7)
