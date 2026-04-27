"""
ClerkAccount profile model.

Maps a Django :class:`django.contrib.auth.models.User` to its stable Clerk
identity (the JWT ``sub`` claim). This profile pattern keeps Clerk-specific
fields off the ``auth.User`` table, leaves Django's ``username`` free of
external-identifier semantics, and gives downstream code a single, indexed
lookup column for the canonical IdP identifier.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


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
