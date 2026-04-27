# Lazy User Sync

Authenticated requests carry a validated JWT. Most reads only need the
claims — and we want those reads to stay free of database hits. This page
explains when to upgrade from the lightweight principal to a persisted
`User` row, and how to do it.

## The two objects

| Object | Backed by | DB hit? | Use for |
|---|---|---|---|
| `JWTPrincipal` | The decoded JWT claims | No | Permission checks, identity for read-only endpoints, anything that just needs the `sub` or `permissions` claim. |
| `User` (Django auth) | A row in the `auth_user` table | Yes (first access per request) | Foreign keys, audit fields (`created_by`, `updated_by`), Django admin integration, anything that needs a stable PK. |

The principal is what `JWKSAuthentication` returns. The `User` is what you
get when you actually need persistence — accessed via `principal.user` (a
`cached_property`) or directly via `get_or_create_user_from_claims()`.

## When to use which

**Use the principal (no DB hit)** for:

- Permission checks via `HasAPIPermission` (already automatic — the class
  reads `request.auth`).
- Read endpoints whose response doesn't depend on the local user row.
- Any code path where you only need `sub`, `email`, or `permissions` from
  the token.

**Upgrade to the user row** when you need to:

- Set a `ForeignKey(settings.AUTH_USER_MODEL)` (e.g. `created_by`,
  `owned_by`, `assigned_to`).
- Write an audit log entry that references the user by PK.
- Hand the request off to code that expects `request.user` to be a real
  `User` (admin views, third-party packages, signal handlers).
- Send notifications or otherwise act on email — even though the principal
  carries email in claims, going through the user row gives you the
  canonical (and admin-editable) value.

When in doubt, prefer the principal. Adding a DB hit later is one line;
removing one requires a refactor.

## How to upgrade

Easiest — read it off the principal that DRF already attached:

```python
def perform_create(self, serializer):
    # request.user is the JWTPrincipal; .user lazy-syncs to a Django User.
    serializer.save(created_by=self.request.user.user)
```

Or call the helper directly when you have raw claims (e.g. in a
non-DRF view, a Celery task, etc.):

```python
from gam.auth.sync import get_or_create_user_from_claims

user = get_or_create_user_from_claims(claims)
```

The helper is idempotent: first call creates the `User` and a
`ClerkAccount` row; subsequent calls return the same `User` and refresh
the cached email if it changed.

## The data model

```
django.contrib.auth.User
   ▲ OneToOne
   │
ClerkAccount
   ├── user (FK)
   ├── clerk_sub  (unique, indexed) ← canonical lookup
   ├── email      (cached from token)
   ├── created_at
   └── updated_at
```

The Clerk `sub` claim is the **stable external identifier** — it never
changes for the life of the user. Always look users up via
`ClerkAccount.clerk_sub`, not by email (which can change) and not by
`User.username` (which is a synthetic placeholder we don't promise the
shape of).

## Backfill

If you already have Django users that predate Clerk integration (most
likely a superuser created via `createsuperuser`), associate them with
their Clerk identity using the management command:

```bash
uv run manage.py backfill_clerk_sub --email=admin@griddy.test --sub=user_2abcDEF...
```

The command:

- Looks up the Django user by email (case-insensitive).
- Refuses if the `sub` is already linked to a different user.
- Refuses if the user already has a `ClerkAccount` unless you also pass
  `--update-email` to refresh the cached email.

Most installations will never need to run this — newly authenticated
Clerk users get synced automatically on first access to `principal.user`.
