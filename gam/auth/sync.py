"""
Lazy Django user sync from validated JWT claims (TGF-317).

Hot-path requests are handled by :class:`gam.auth.jwt.JWKSAuthentication`,
which returns a lightweight :class:`~gam.auth.jwt.JWTPrincipal` and never
touches the database. When a view actually needs a persisted ``User`` row
(foreign keys, audit trails, anything ``django.contrib.auth`` integrates
with), it calls :func:`get_or_create_user_from_claims` to upsert one.

The Clerk ``sub`` claim is the stable external identifier — it never
changes for the life of the user. The mapping lives on
:class:`gam.accounts.models.ClerkAccount`; ``User.username`` is a synthetic
placeholder and should not be relied on by lookup code.
"""

from __future__ import annotations

import secrets
from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction


class MissingSubjectClaim(ValueError):
    """Raised when sync is attempted on a token with no ``sub`` claim."""


def _generate_username(sub: str) -> str:
    """Return a synthetic, unique username derived from ``sub``.

    Username carries no business meaning here; it exists only because
    Django's :class:`~django.contrib.auth.models.User` model requires one.
    Lookups must go through :class:`~gam.accounts.models.ClerkAccount.clerk_sub`,
    not :attr:`User.username`.
    """
    # Random suffix prevents collisions if a sub is ever reissued or if
    # an admin manually creates a user with a clashing username.
    return f"clerk-{sub[:24]}-{secrets.token_hex(4)}"


@transaction.atomic
def get_or_create_user_from_claims(claims: dict[str, Any]):
    """Return the local ``User`` row for the JWT principal, creating it if needed.

    On first call for a given ``sub``, a new ``User`` and ``ClerkAccount``
    are created. On subsequent calls, the existing pair is returned and the
    cached email is refreshed if the token reports a different one.

    The function is wrapped in ``transaction.atomic`` so partial creates
    (User saved, ClerkAccount creation fails) cannot leak orphaned rows.
    """
    sub = claims.get("sub")
    if not sub:
        raise MissingSubjectClaim("Token has no `sub` claim; cannot sync user.")
    email = (claims.get("email") or "").strip()

    from gam.accounts.models import ClerkAccount

    User = get_user_model()
    try:
        account = ClerkAccount.objects.select_related("user").get(clerk_sub=sub)
    except ClerkAccount.DoesNotExist:
        try:
            user = User.objects.create_user(
                username=_generate_username(sub),
                email=email,
            )
            ClerkAccount.objects.create(user=user, clerk_sub=sub, email=email)
        except IntegrityError:
            # Lost a race with a concurrent request for the same sub —
            # fall through to the read path.
            account = ClerkAccount.objects.select_related("user").get(clerk_sub=sub)
        else:
            return user

    _sync_email(account, email)
    return account.user


def _sync_email(account, email: str) -> None:
    """Refresh cached email on User and ClerkAccount when the token reports a change."""
    if not email:
        return
    user_changed = account.user.email != email
    account_changed = account.email != email
    if user_changed:
        account.user.email = email
        account.user.save(update_fields=["email"])
    if account_changed:
        account.email = email
        account.save(update_fields=["email", "updated_at"])
