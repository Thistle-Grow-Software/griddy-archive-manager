"""
Backfill a :class:`ClerkAccount` row for an existing Django user.

Use this when a Django ``User`` predates the Clerk integration and you want
to associate it with a Clerk identity without forcing them through a fresh
sign-in. Most installations will never need to run this — it's here mainly
for superusers created via ``createsuperuser`` before TGF-317 landed.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from gam.accounts.models import ClerkAccount


class Command(BaseCommand):
    help = "Create a ClerkAccount for an existing Django user identified by email."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--email",
            required=True,
            help="Email address of the existing Django user.",
        )
        parser.add_argument(
            "--sub",
            required=True,
            help="Clerk `sub` claim value to associate (e.g. user_2abcDEF...).",
        )
        parser.add_argument(
            "--update-email",
            action="store_true",
            help=(
                "If a ClerkAccount already exists for this sub, update its "
                "cached email to the value passed via --email."
            ),
        )

    def handle(self, *args, **options) -> None:
        email: str = options["email"].strip()
        sub: str = options["sub"].strip()
        update_email: bool = options["update_email"]

        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist as exc:
            raise CommandError(f"No user found with email {email!r}.") from exc
        except User.MultipleObjectsReturned as exc:
            raise CommandError(
                f"Multiple users share email {email!r}; resolve manually."
            ) from exc

        try:
            with transaction.atomic():
                account = ClerkAccount.objects.create(
                    user=user, clerk_sub=sub, email=email
                )
        except IntegrityError as exc:
            # Inner atomic rolled back; outer DB connection is still healthy.
            existing = ClerkAccount.objects.filter(clerk_sub=sub).first()
            if existing and existing.user_id != user.id:
                raise CommandError(
                    f"clerk_sub {sub!r} is already linked to user "
                    f"{existing.user_id}; refusing to clobber."
                ) from exc
            if not update_email:
                raise CommandError(
                    f"User {user.id} already has a ClerkAccount; pass "
                    f"--update-email to refresh the cached email."
                ) from exc
            account = ClerkAccount.objects.get(user=user)
            account.email = email
            account.save(update_fields=["email", "updated_at"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated ClerkAccount for user {user.id} (sub={sub})."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Linked user {user.id} ({email}) to clerk_sub {sub} "
                f"(account id {account.id})."
            )
        )
