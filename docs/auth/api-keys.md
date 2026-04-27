# API Keys

API keys are the auth path for **SDK** and **machine-to-machine**
access — code calling the Griddy API from your own backend, a CI job,
or any context with no end user in the loop. If your code is acting on
behalf of a signed-in user, see [JWT Authentication](jwt.md) instead.

## Token format

```
grd_{environment}_{48 hex chars}
```

- `environment` is `live` or `test`. Test keys are an intent signal —
  "ok to embed in CI fixtures, dev sandboxes, demo recordings." Live
  keys signal production credentials and should be treated as such.
  Both hit the same database; the prefix is informational, not
  isolating.
- 48 hex chars = 192 bits of entropy.
- The `grd_` scheme prefix is intentional so leaked credentials are
  easy to spot in source code, log dumps, and GitHub's secret scanner.

Example: `grd_live_a1b2c3d4e5f607182930414253647586a7b8c9d0e1f20304`.

## Issuing a key

### Via the API

```bash
curl -X POST https://api.griddy.test/api/v1/api-keys/ \
  -H "Authorization: Bearer $CLERK_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CI server",
    "environment": "live",
    "scopes": ["catalog:read"],
    "expires_at": "2027-01-01T00:00:00Z"
  }'
```

Response:

```json
{
  "api_key": {
    "id": 42,
    "name": "CI server",
    "environment": "live",
    "key_prefix": "grd_live_a1b2c3d4",
    "scopes": ["catalog:read"],
    "created_at": "2026-04-27T13:00:00Z",
    "last_used_at": null,
    "expires_at": "2027-01-01T00:00:00Z",
    "revoked_at": null,
    "is_active": true
  },
  "plaintext": "grd_live_a1b2c3d4e5f607182930414253647586a7b8c9d0e1f20304",
  "warning": "Store this token now — it will not be shown again. If you lose it, revoke this key and issue a new one."
}
```

The plaintext token is in the `plaintext` field. It is shown **exactly
once** — there's no API for retrieving it later. If you lose it,
revoke the key and issue a new one.

Issuance requires a Clerk session token, not another API key. This is a
deliberate guard against privilege escalation — see
[Why API keys can't manage other API keys](#why-api-keys-cant-manage-other-api-keys).

### Via the dashboard (when available)

A dashboard for issuing and managing keys is in flight (TGF-343). Until
it ships, use the API directly.

## Using a key

```bash
curl -H "Authorization: Bearer grd_live_..." \
     https://api.griddy.test/api/v1/leagues/
```

Same header, same shape, same endpoint set as JWT auth. The server
picks the right verifier based on the `grd_` prefix.

```python
import os
import requests

response = requests.get(
    "https://api.griddy.test/api/v1/leagues/",
    headers={"Authorization": f"Bearer {os.environ['GRIDDY_API_KEY']}"},
    timeout=10,
)
response.raise_for_status()
print(response.json())
```

```typescript
const response = await fetch("https://api.griddy.test/api/v1/leagues/", {
  headers: {
    Authorization: `Bearer ${process.env.GRIDDY_API_KEY}`,
  },
});
const data = await response.json();
```

Always source the token from an environment variable or a secrets
manager. Never check it into a repo, even briefly — GitHub's secret
scanner will flag the `grd_` prefix and revoke it on push.

## Listing your keys

```bash
curl -H "Authorization: Bearer $CLERK_SESSION_TOKEN" \
     https://api.griddy.test/api/v1/api-keys/
```

Returns every key your account owns, **without** the plaintext. You'll
get the prefix, scopes, and lifecycle timestamps — enough to identify
which key is which when revoking.

## Revoking

```bash
curl -X POST https://api.griddy.test/api/v1/api-keys/42/revoke/ \
  -H "Authorization: Bearer $CLERK_SESSION_TOKEN"
```

Revocation is **immediate and permanent**. The next request bearing
that token gets `401 API key has been revoked.` Calling revoke twice
is idempotent — the second call returns `200` with the existing
`revoked_at` timestamp.

Revoke a key:

- Before you suspect it's leaked, not after — proactive rotation is
  the cheap option.
- Whenever an integration is decommissioned.
- When an employee with access to the key leaves.

## Scopes

API keys carry scopes from the same catalog as JWT permissions —
`catalog:read`, `catalog:write`, `holdings:read`, `holdings:write`. See
[Permissions](permissions.md) for the full list and what each grants.

Issue every key with the **minimum** scope its integration actually
needs. A read-only dashboard should not get `catalog:write`. A
data-ingest pipeline that touches only catalog resources should not get
`holdings:*`.

## Lifecycle

| Field | Meaning |
|---|---|
| `created_at` | When the key was issued. |
| `last_used_at` | Approximate timestamp of most recent successful authentication. Updates are batched (~1 write per key per minute), so don't rely on second-level precision. |
| `expires_at` | Optional. Once past, the key is rejected with `401`. |
| `revoked_at` | Set when revoked. Once set, never unset. |

`is_active` in the response body is a convenience flag —
`!is_revoked && !is_expired`.

## Why API keys can't manage other API keys

A key cannot mint, list, revoke, or modify keys via `/api/v1/api-keys/`
— that endpoint requires a Clerk session token (the human account
owner). The reasoning:

- A leaked key with management scope could mint replacement keys, hide
  its tracks by revoking and re-issuing, and survive the legitimate
  owner's revocation attempt.
- The fix is structural, not scope-based: management endpoints simply
  don't accept API key auth. Full stop.

If you need a service-to-service flow that includes key management,
that's a higher-trust pattern (e.g., a signed admin token from your
own auth server) — not something to bolt onto API key scopes.

## Operational notes

- **Rotate before you're sure you need to.** The cost of rotation is
  one CI redeploy; the cost of a leaked-and-not-rotated key is
  proportional to how long it's been leaked.
- **Test keys are not isolated.** They share the same database and
  permission model as live keys. The `test` prefix is for *intent*
  ("ok to share in screenshots") not for sandboxing.
- **One key per integration.** Resist the urge to share a key across
  multiple consumers — it makes revocation surgical instead of
  cataclysmic when you need to remove access for one of them.
- **Never log the plaintext.** Log `key_prefix` if you need to
  correlate; the prefix uniquely identifies a key without exposing it.
