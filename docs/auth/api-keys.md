# API Keys

API keys are the auth path for **SDK** and **machine-to-machine** access —
developers calling the Griddy API from their own backend with no end-user
in the loop. Browser-driven access continues to use Clerk JWTs (see
[API Authentication](../api-authentication.md)).

## Token format

```
grd_{environment}_{48 hex chars}
```

- `environment` is `live` or `test`. Test keys signal "ok to embed in CI
  fixtures, dev sandboxes, demo recordings"; live keys signal "production
  credentials, treat carefully."
- The 48-hex-char body is `secrets.token_hex(24)` — 192 bits of entropy.
- Total length is ~57 chars. The `grd_` scheme prefix is intentional so
  leaked credentials are easy to spot in source code, log dumps, and
  GitHub's secret scanner.

Example: `grd_live_a1b2c3d4e5f607182930414253647586a7b8c9d0e1f20304`.

## Storage model

Only the **hash** of the token lives in the database. The plaintext is
returned exactly once at issuance and never recoverable.

```
APIKey
├── account       (FK → ClerkAccount)
├── name          (operator-facing label)
├── environment   (live | test)
├── key_prefix    (indexed, ~17 chars: `grd_{env}_{first 8 hex}`)
├── key_hash      (SHA-256 of full plaintext, hex)
├── scopes        (JSON list using the TGF-316 catalog)
├── created_at
├── last_used_at  (deferred, throttled — see below)
├── expires_at    (optional)
└── revoked_at    (optional)
```

We use SHA-256, not bcrypt/argon2, because the input is high-entropy
random — a slow KDF only buys you anything when the input is a
low-entropy human password. Brute-forcing a 192-bit key against a stored
hash is not the threat model.

## Authentication flow

`gam.auth.api_key.APIKeyAuthentication` sits in
`DEFAULT_AUTHENTICATION_CLASSES` alongside `JWKSAuthentication`. Both
accept `Authorization: Bearer <token>`; each returns `None` for tokens
that don't match its scheme so the next class can try:

1. Token starts with `grd_` → API key path. Otherwise → JWT path.
2. Strict regex check on shape; malformed tokens fail fast.
3. Compute `key_prefix` from the presented secret, look up candidates by
   the indexed prefix column.
4. SHA-256 the full token and compare against each candidate's `key_hash`
   using `hmac.compare_digest` (constant time — no timing leak about
   which candidate matched).
5. Reject revoked or expired keys with `AuthenticationFailed`.
6. On success, set `request.user = ClerkAccount` and `request.auth =
   APIKey`. Permission checks read scopes off `request.auth.scopes`.

## Scopes

API key scopes use the **same string catalog** as JWT permissions
(`catalog:read`, `catalog:write`, `holdings:read`, `holdings:write` —
see [Permission Catalog](permissions.md)). `HasAPIPermission` accepts
permissions from either source — viewsets don't need to know which auth
path the request came in on.

Issue keys with the minimum scope an integration actually needs.
Read-only dashboards get `["catalog:read"]`; ingestion pipelines get
read + write for the relevant domain. Avoid issuing all four on a key
that only needs one.

## Lifecycle

### Issuance

```bash
POST /api/v1/api-keys/
{
  "name": "CI server",
  "environment": "live",
  "scopes": ["catalog:read"],
  "expires_at": "2027-01-01T00:00:00Z"   // optional
}
```

Response includes the plaintext token under `plaintext` and a `warning`
field reminding the operator it will not be shown again.

### Revocation

```bash
POST /api/v1/api-keys/{id}/revoke/
```

Idempotent — calling it on an already-revoked key returns `200` with the
existing `revoked_at`. Once revoked, the next request bearing that
token gets `401 API key has been revoked.`

### Last-used tracking

`last_used_at` updates are deferred via `transaction.on_commit` and
throttled to at most one write per key per
`LAST_USED_THROTTLE_SECONDS` (default 60s). The throttle lives in a
single conditional `UPDATE`, so a high-RPS key produces at most one
write per minute regardless of request rate.

## Privilege escalation guard

API keys **cannot manage other API keys**. The `/api/v1/api-keys/`
endpoints require a Clerk JWT principal (`IsJWTPrincipal` permission
class). A stolen or leaked key cannot be used to mint replacement keys
or hide its tracks — the legitimate account holder must sign in via
Clerk to do that.

## When to use which auth

| Scenario | Auth path |
|---|---|
| Browser-driven UI, real end user | Clerk session token (JWT) |
| SDK call from a developer's backend | API key |
| CI / CD pipelines | API key (test or live, depending on env) |
| Internal scripts / data-science notebooks | API key |
| Webhooks signed by a third-party (future) | HMAC over body, not covered here |

If the integration impersonates a user, use a JWT. If it acts as the
account itself, use an API key.

## Operational notes

- Rotate keys before they're suspected of being leaked, not after. The
  cost is one CI redeploy.
- Treat test keys like passwords too — they hit a real DB; `test` is a
  signal about *intent*, not isolation.
- Keys are scoped to the requesting `ClerkAccount`. Cross-account access
  requires a separate key issued by that account's owner.
