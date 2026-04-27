# Errors & Troubleshooting

Two response codes carry all the auth-related signal:

- **`401 Unauthorized`** — we couldn't authenticate the request at all.
  Either no token was provided, or the token was invalid (expired,
  wrong signature, malformed, revoked, …).
- **`403 Forbidden`** — we know who you are, but the token doesn't carry
  the permission this endpoint requires.

`401` says "fix your token." `403` says "ask for more scope."

## Reading error responses

The API returns JSON for every auth failure with a single `detail` key
explaining what went wrong:

```json
{
  "detail": "Token has expired."
}
```

The exact strings appear below — they're stable and safe to match on
in client error handling.

## 401 — authentication failures

These come from one of the auth classes (`JWKSAuthentication` for JWTs,
`APIKeyAuthentication` for API keys) before any permission check runs.

| Detail message | Cause | Fix |
|---|---|---|
| (no `WWW-Authenticate` body, just 401) | No `Authorization` header was sent. | Include `Authorization: Bearer <token>`. |
| `Token has expired.` | The JWT's `exp` claim is in the past. | Mint a fresh token. Clerk session tokens default to ~60s. |
| `Invalid audience.` | The JWT's `aud` claim doesn't match what the API expects. | Configure your token's audience to match the deployment, or use the default Clerk session token (don't pass a custom JWT template). |
| `Invalid issuer.` | The JWT's `iss` claim doesn't match. | Confirm the JWT is from the correct Clerk instance. |
| `Invalid signature.` | The JWT was signed with a key not in the published JWKS. | Token came from a different Clerk instance than the API is configured for. |
| `Invalid signing algorithm.` | The JWT uses something other than `RS256`. | Use a Clerk-issued token; we don't accept HS256 or other symmetric algorithms. |
| `Invalid authorized party.` | The deployment configured allowed `azp` values, and your token's `azp` isn't one of them. | Use a frontend-issued token, or ask the deployment owner to add your origin to the allowlist. Backend-API-minted tokens have no `azp` claim and will fail this check when the allowlist is non-empty. |
| `Malformed API key.` | The bearer token starts with `grd_` but doesn't match the expected shape. | Confirm the token is the full string returned at issuance — look for whitespace, missing characters, or a copy-paste error. |
| `API key has been revoked.` | The key was revoked via the dashboard or revoke endpoint. | Issue a new key. The old one is dead permanently. |
| `API key has expired.` | The key's `expires_at` is in the past. | Issue a new key. If you didn't set an expiry and still see this, check whether the deployment enforces a global key TTL. |
| `Invalid API key.` | Token shape was correct but the hash didn't match any active key. | The key was deleted, or the token is from a different environment (e.g. you're sending a `grd_test_*` key to a production deployment that only accepts `grd_live_*`). |

## 403 — authorization failures

These come from the permission class after authentication has succeeded.
They almost always look like:

```json
{
  "detail": "Token is missing one or more required permissions."
}
```

This means the token is valid, but it doesn't carry the permission
string the endpoint requires. Common causes:

- **You used the wrong scope.** E.g., `holdings:read` won't let you list
  catalog resources — those need `catalog:read`. See
  [Permissions](permissions.md) for the full mapping.
- **You only granted read.** Write endpoints (`POST`, `PUT`, `PATCH`,
  `DELETE`) require `*:write`, not `*:read`. They're separate scopes
  even within the same domain.
- **The Clerk session token doesn't carry permissions yet.** If you
  haven't added the `permissions` claim under
  **Sessions → Customize session token**, every endpoint will return
  `403` for valid Clerk tokens. See [JWT Authentication](jwt.md).

## Debugging checklist

When a request unexpectedly fails, walk through this list:

1. **Is the token actually being sent?** Inspect the request in your
   browser dev tools or `curl -v`. The first hop is "did the header
   arrive."
2. **Is it the right shape?** API keys start with `grd_live_` or
   `grd_test_`. JWTs have exactly two `.` separators
   (`header.payload.signature`).
3. **Decode the JWT (if applicable)** at [jwt.io](https://jwt.io) or
   with a local tool. Verify `iss`, `aud`, `exp`, and `permissions` are
   what you expect.
4. **For API keys, confirm the environment.** A `grd_test_*` key won't
   authenticate against a deployment that's been pinned to live keys.
5. **For 403s, check the `permissions` / `scopes` array.** The string
   has to match exactly — `catalog:read` and `catalog.read` are not
   the same thing.
6. **Try the same request with curl.** If curl works and your client
   doesn't, the bug is client-side (likely header construction or token
   handling).

## When to ask for help

If you've decoded the token, confirmed every claim, and the API still
rejects the request: that's a real bug or a deployment misconfiguration,
not a usage error. File an issue on the relevant repo with:

- The full `detail` string from the response.
- The decoded (header + payload) view of the token, **with the
  signature redacted**.
- The endpoint URL and HTTP method.
- Approximate UTC timestamp of the failed request (for log correlation).

Never include a live token, an API key, or the JWT signature in a bug
report — treat them like passwords.
