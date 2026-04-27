"""
Tests for the lazy Django user sync helper and JWTPrincipal.user property
(TGF-317).
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from gam.accounts.models import ClerkAccount
from gam.auth.jwt import JWTPrincipal
from gam.auth.sync import (
    MissingSubjectClaim,
    get_or_create_user_from_claims,
)

pytestmark = pytest.mark.django_db


User = get_user_model()


# ---------------------------------------------------------------------------
# get_or_create_user_from_claims
# ---------------------------------------------------------------------------


class TestGetOrCreateUserFromClaims:
    def test_creates_user_and_account_for_new_sub(self):
        user = get_or_create_user_from_claims(
            {"sub": "user_new_1", "email": "new@griddy.test"}
        )
        assert user.email == "new@griddy.test"
        account = ClerkAccount.objects.get(user=user)
        assert account.clerk_sub == "user_new_1"
        assert account.email == "new@griddy.test"

    def test_returns_existing_user_for_known_sub(self):
        first = get_or_create_user_from_claims(
            {"sub": "user_known", "email": "u@griddy.test"}
        )
        second = get_or_create_user_from_claims(
            {"sub": "user_known", "email": "u@griddy.test"}
        )
        assert first.pk == second.pk
        assert ClerkAccount.objects.filter(clerk_sub="user_known").count() == 1

    def test_email_change_updates_user_and_account(self):
        user = get_or_create_user_from_claims(
            {"sub": "user_email_1", "email": "old@griddy.test"}
        )
        again = get_or_create_user_from_claims(
            {"sub": "user_email_1", "email": "new@griddy.test"}
        )
        assert again.pk == user.pk
        again.refresh_from_db()
        assert again.email == "new@griddy.test"
        account = ClerkAccount.objects.get(user=again)
        assert account.email == "new@griddy.test"

    def test_missing_email_does_not_clobber_existing_email(self):
        user = get_or_create_user_from_claims(
            {"sub": "user_keep_email", "email": "kept@griddy.test"}
        )
        # Subsequent token without an email — must not blank the cached one.
        get_or_create_user_from_claims({"sub": "user_keep_email"})
        user.refresh_from_db()
        assert user.email == "kept@griddy.test"

    def test_creates_user_when_email_absent(self):
        user = get_or_create_user_from_claims({"sub": "user_no_email"})
        assert user.email == ""
        assert ClerkAccount.objects.filter(clerk_sub="user_no_email").exists()

    def test_username_does_not_equal_sub(self):
        """Lookups must go via clerk_sub; username stays opaque."""
        user = get_or_create_user_from_claims({"sub": "user_username_check"})
        assert user.username != "user_username_check"
        assert "user_username_check"[:24] in user.username  # derived, not equal

    def test_missing_sub_raises(self):
        with pytest.raises(MissingSubjectClaim):
            get_or_create_user_from_claims({"email": "no-sub@griddy.test"})

    def test_empty_sub_raises(self):
        with pytest.raises(MissingSubjectClaim):
            get_or_create_user_from_claims({"sub": "", "email": "x@griddy.test"})

    def test_two_subs_get_distinct_users(self):
        a = get_or_create_user_from_claims({"sub": "user_a"})
        b = get_or_create_user_from_claims({"sub": "user_b"})
        assert a.pk != b.pk

    def test_email_whitespace_is_stripped(self):
        user = get_or_create_user_from_claims(
            {"sub": "user_ws", "email": "  trimmed@griddy.test  "}
        )
        assert user.email == "trimmed@griddy.test"


# ---------------------------------------------------------------------------
# JWTPrincipal.user
# ---------------------------------------------------------------------------


class TestJWTPrincipalUserProperty:
    def test_property_returns_synced_user(self):
        principal = JWTPrincipal(claims={"sub": "user_principal_1"})
        user = principal.user
        assert user.pk is not None
        assert ClerkAccount.objects.get(clerk_sub="user_principal_1").user_id == user.pk

    def test_property_is_cached(self):
        principal = JWTPrincipal(claims={"sub": "user_principal_cache"})
        first = principal.user
        # Second access must not create another User row even if we delete the
        # ClerkAccount under the principal.
        ClerkAccount.objects.filter(clerk_sub="user_principal_cache").delete()
        second = principal.user
        assert first is second

    def test_property_does_not_trigger_on_unrelated_attribute_access(self):
        """Reading non-user fields on the principal must not hit the DB."""
        principal = JWTPrincipal(claims={"sub": "user_lazy", "email": "x@y"})
        assert principal.subject == "user_lazy"
        assert principal.is_authenticated is True
        # User row should not exist yet.
        assert not ClerkAccount.objects.filter(clerk_sub="user_lazy").exists()


# ---------------------------------------------------------------------------
# Backfill management command
# ---------------------------------------------------------------------------


class TestBackfillCommand:
    def test_links_existing_user(self):
        user = User.objects.create_user(username="legacy", email="legacy@griddy.test")
        call_command(
            "backfill_clerk_sub",
            "--email=legacy@griddy.test",
            "--sub=user_legacy_sub",
        )
        account = ClerkAccount.objects.get(clerk_sub="user_legacy_sub")
        assert account.user_id == user.pk
        assert account.email == "legacy@griddy.test"

    def test_email_lookup_is_case_insensitive(self):
        User.objects.create_user(username="u1", email="Mixed@Griddy.Test")
        call_command(
            "backfill_clerk_sub",
            "--email=mixed@griddy.test",
            "--sub=user_mixed",
        )
        assert ClerkAccount.objects.filter(clerk_sub="user_mixed").exists()

    def test_unknown_email_fails(self):
        with pytest.raises(CommandError, match="No user"):
            call_command(
                "backfill_clerk_sub",
                "--email=ghost@griddy.test",
                "--sub=user_ghost",
            )

    def test_existing_account_without_update_flag_fails(self):
        user = User.objects.create_user(username="dup", email="dup@griddy.test")
        ClerkAccount.objects.create(
            user=user, clerk_sub="user_dup", email="dup@griddy.test"
        )
        with pytest.raises(CommandError, match="already has"):
            call_command(
                "backfill_clerk_sub",
                "--email=dup@griddy.test",
                "--sub=user_dup",
            )

    def test_existing_account_with_update_flag_refreshes_email(self):
        user = User.objects.create_user(username="refresh", email="old@griddy.test")
        ClerkAccount.objects.create(
            user=user, clerk_sub="user_refresh", email="old@griddy.test"
        )
        call_command(
            "backfill_clerk_sub",
            "--email=old@griddy.test",
            "--sub=user_refresh",
            "--update-email",
        )
        account = ClerkAccount.objects.get(user=user)
        assert account.email == "old@griddy.test"

    def test_sub_already_linked_to_other_user_fails(self):
        a = User.objects.create_user(username="a", email="a@griddy.test")
        User.objects.create_user(username="b", email="b@griddy.test")
        ClerkAccount.objects.create(
            user=a, clerk_sub="user_taken", email="a@griddy.test"
        )
        with pytest.raises(CommandError, match="already linked"):
            call_command(
                "backfill_clerk_sub",
                "--email=b@griddy.test",
                "--sub=user_taken",
            )
