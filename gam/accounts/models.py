"""
Account models: ClerkAccount (human identity) and APIKey (M2M / SDK auth).

ClerkAccount maps a Django :class:`django.contrib.auth.models.User` to its
stable Clerk identity (the JWT ``sub`` claim). APIKey gives those accounts
long-lived, hashed credentials for SDK and machine-to-machine access.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class ClerkAccount(models.Model):
    """One-to-one bridge between a Django User and its Clerk identity."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clerk_account",
    )
    # Clerk's `sub` claim — stable, never changes for the life of the user.
    # Always look up users via this column, not via ``User.username`` or email.
    clerk_sub = models.CharField(max_length=255, unique=True, db_index=True)
    # Cached email from the most recent JWT. May lag behind Clerk briefly;
    # the sync helper refreshes it whenever a token with a new email arrives.
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Clerk account"
        verbose_name_plural = "Clerk accounts"

    def __str__(self) -> str:
        return f"{self.clerk_sub} ({self.user_id})"


class APIKeyEnvironment(models.TextChoices):
    LIVE = "live", "Live"
    TEST = "test", "Test"


class APIKey(models.Model):
    """A hashed, scoped, revocable credential for SDK / M2M API access.

    The plaintext key is shown to the operator exactly once at issuance and
    never persisted. Lookups use ``key_prefix`` (indexed) to narrow
    candidates, then constant-time compare the SHA-256 of the presented
    token against ``key_hash``. Keys are high-entropy random — SHA-256 is
    appropriate; no need for a slow KDF (argon2/bcrypt are for low-entropy
    user passwords).
    """

    account = models.ForeignKey(
        ClerkAccount,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable label (e.g. 'CI server', 'Local dev').",
    )
    environment = models.CharField(
        max_length=8,
        choices=APIKeyEnvironment.choices,
        default=APIKeyEnvironment.LIVE,
    )
    # Indexed lookup hint of the form ``grd_{env}_{first 8 hex of secret}``.
    # Two keys with the same prefix are possible but rare; the auth path
    # disambiguates by hashing the presented token and comparing to all
    # candidates with constant-time compare.
    key_prefix = models.CharField(max_length=24, db_index=True)
    # Hex SHA-256 of the full plaintext token. 64 chars.
    key_hash = models.CharField(max_length=128)
    scopes = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Permission strings using the same catalog as JWT tokens "
            "(e.g. ['catalog:read'])."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "API key"
        verbose_name_plural = "API keys"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        suffix = " [revoked]" if self.is_revoked else ""
        return f"{self.name} ({self.key_prefix}…){suffix}"

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_active(self) -> bool:
        return not (self.is_revoked or self.is_expired)
