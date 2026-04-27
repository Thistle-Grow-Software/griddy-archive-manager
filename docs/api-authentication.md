# API Authentication

GAM's REST API uses bearer JWTs validated against a JWKS endpoint
(`gam.auth.jwt.JWKSAuthentication`). In production this is wired to a
[Clerk](https://clerk.com) instance, but the auth class is IdP-agnostic — any
JWKS-based issuer works.

This page covers how to obtain a token for hitting the API from scripts,
`curl`, `httpie`, integration tests, or CI.

## Settings

The DRF auth class reads these Django settings (sourced from environment
variables in `gam/settings.py`):

| Setting | Env var | Purpose |
|---|---|---|
| `JWKS_URL` | `CLERK_JWKS_URL` | JWKS endpoint to fetch signing keys from |
| `JWT_ISSUER` | `CLERK_ISSUER` | Required `iss` claim |
| `JWT_AUDIENCE` | `CLERK_AUDIENCE` | Required `aud` claim |
| `JWT_AUTHORIZED_PARTIES` | `CLERK_AUTHORIZED_PARTIES` | Comma-separated allowed `azp` values; skipped if empty |
| `CLERK_SECRET_KEY` | `CLERK_SECRET_KEY` | Backend API key (token minting only) |

A request authenticates by sending `Authorization: Bearer <jwt>`. If the
header is missing the request falls through to anonymous; if it is present
but invalid the request is rejected with `401`.

## Option 1 — Mint a Clerk token via Backend API

For local dev or CI against a Clerk *development* instance, use the helper
script at `scripts/mint_clerk_token.py`. It creates a session for an existing
Clerk user and exchanges it for a JWT in two Backend API calls.

### Prerequisites

- `CLERK_SECRET_KEY` set to your Clerk dev instance secret key.
- A Clerk user ID (e.g. `user_2abcDEF...`) — find one in the Clerk dashboard.
- The same Clerk instance configured on the Django side (`CLERK_JWKS_URL`,
  `CLERK_ISSUER`, `CLERK_AUDIENCE`).

### Usage

```bash
export CLERK_SECRET_KEY=sk_test_...

# Default session token:
python scripts/mint_clerk_token.py --user-id user_2abcDEF...

# Token shaped by a specific Clerk JWT template (matches GAM's audience):
python scripts/mint_clerk_token.py --user-id user_2abcDEF... --template griddy-api

# Inline into a curl call:
TOKEN=$(python scripts/mint_clerk_token.py --user-id user_2abcDEF...)
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/leagues/
```

The token is printed to stdout on success; errors go to stderr with a
non-zero exit code.

### Unset `CLERK_AUTHORIZED_PARTIES` for this flow

Backend-API-minted tokens do **not** carry an `azp` claim — Clerk only sets
`azp` on tokens issued through the Frontend API, where the requesting origin
is known. If `CLERK_AUTHORIZED_PARTIES` is set in your local env, the
`_enforce_authorized_party` check will reject these tokens with
`Invalid authorized party.`

Leave the var unset (or empty) in local `.env` files; the auth class skips
the check when the setting is empty. Keep it populated in production, where
all real traffic comes through the frontend.

### When this does *not* work

Clerk **production** instances reject `POST /v1/sessions` with a
`actor_token_creation_unauthorized`-style error. For production-like testing,
either point the script at a dev instance or sign in through the frontend and
copy the token from `useAuth().getToken()` in the browser.

## Option 2 — Local JWKS server (no Clerk required)

When you want to exercise auth without any IdP at all, use
`scripts/local_jwks_server.py`. It generates a fresh RSA keypair, serves a
JWKS document, and prints a signed JWT — the Django app just needs to point
its `JWKS_URL`/`JWT_ISSUER`/`JWT_AUDIENCE` at the local server's defaults.

```bash
# Terminal 1 — serve JWKS and emit a token:
python scripts/local_jwks_server.py --issue

# Terminal 2 — point Django at it:
export JWKS_URL=http://127.0.0.1:8765/.well-known/jwks.json
export JWT_ISSUER=https://local.griddy.test
export JWT_AUDIENCE=griddy-api-local
curl -H "Authorization: Bearer <token-from-terminal-1>" \
     http://127.0.0.1:8000/api/v1/leagues/
```

Tokens do not survive a server restart — the keypair is regenerated each
time. This is intentional: the script is a dev aid, not a persistent IdP.

## Option 3 — Frontend session token

For browser-driven testing or when integrating a real frontend, call
`getToken()` from Clerk's React/Next SDK:

```typescript
import { useAuth } from "@clerk/clerk-react";

const { getToken } = useAuth();
const token = await getToken();              // default session token
const apiToken = await getToken({ template: "griddy-api" }); // custom template
```

Pass the result through as `Authorization: Bearer <token>` on `fetch` calls.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Invalid issuer.` | `CLERK_ISSUER` does not match the token's `iss`. |
| `Invalid audience.` | Token was minted without (or with the wrong) JWT template; set `--template` to one whose audience matches `CLERK_AUDIENCE`. |
| `Invalid authorized party.` | `CLERK_AUTHORIZED_PARTIES` is set but the token's `azp` is missing or not in the list. Backend-API-minted tokens (from `mint_clerk_token.py`) and `local_jwks_server.py` tokens have no `azp` — leave the env var empty for those flows. |
| `Token has expired.` | Mint a fresh one — Clerk session tokens default to ~60s TTL. |
| `Unable to resolve signing key` | `CLERK_JWKS_URL` is wrong or unreachable from the Django process. |
