# JWT Authentication

Use JWTs when an **end user** is signed in and your app is acting on
their behalf. Examples: a browser dashboard, a desktop client with sign-in,
a mobile app. If your code is acting as itself (no end user), use
[API keys](api-keys.md) instead.

The Griddy API verifies tokens issued by [Clerk](https://clerk.com), but
the auth class is IdP-agnostic. Anything that signs RS256 JWTs against
a published JWKS endpoint works.

## What the API expects

Every authenticated request carries:

```
Authorization: Bearer <jwt>
```

The token must:

- Be signed with **RS256** against a key in the configured JWKS endpoint.
- Have an `iss` claim matching the configured issuer.
- Have an `aud` claim matching the configured audience.
- Not be expired (`exp` claim).
- Carry a `permissions` claim covering whatever the endpoint requires.
- Optionally have an `azp` claim if the deployment has configured
  authorized parties.

If any of these fail, the API returns `401`. See
[Errors & Troubleshooting](errors.md) for the specific messages.

## Getting a token

### From a Clerk-authenticated frontend (most common)

In a React or Next.js app that's already wired to Clerk, ask the SDK for
a session token:

```typescript
import { useAuth } from "@clerk/clerk-react";
// or "@clerk/nextjs", "@clerk/clerk-expo", etc.

function MyComponent() {
  const { getToken } = useAuth();

  async function callApi() {
    const token = await getToken();
    const response = await fetch("/api/v1/leagues/", {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.json();
  }
}
```

`getToken()` returns the default session token — that's what the API
expects. Don't pass `template` unless you've created a custom JWT
template for a third-party integration like Supabase or Firebase.

### From a server-side context (backend code, scripts)

If your code is running outside a browser but you still want a JWT
(rather than an API key), Clerk's Backend API can mint a session token
for an existing user:

```bash
# 1. Create a session for the user.
curl -X POST https://api.clerk.com/v1/sessions \
  -H "Authorization: Bearer $CLERK_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_2abcDEF..."}'
# → returns {"id": "sess_xxx", ...}

# 2. Mint a token for that session.
curl -X POST https://api.clerk.com/v1/sessions/sess_xxx/tokens \
  -H "Authorization: Bearer $CLERK_SECRET_KEY"
# → returns {"jwt": "eyJ..."}
```

Two important constraints:

1. **Direct session creation is rejected by Clerk *production* instances.**
   The pattern above works on dev instances; in production, your backend
   should obtain tokens through a real sign-in flow, not by impersonating
   users via the Backend API.
2. **Session tokens default to ~60 second TTL.** Don't cache them; mint
   fresh ones per request or per short batch.

If you find yourself reaching for this pattern in production, that's a
strong signal you should be using an [API key](api-keys.md) instead.

## Where to configure custom claims

If you need additional data on the token (a `permissions` array, custom
flags, organization metadata), add it under
**Sessions → Customize session token** in the Clerk dashboard. Don't use
the JWT Templates section — those are for third-party integrations that
need a different token shape, and they have higher latency.

Suggested permissions claim, sourced from user public metadata:

```json
{
  "permissions": "{{user.public_metadata.permissions}}"
}
```

Or for organization-based RBAC:

```json
{
  "permissions": "{{org_membership.permissions}}"
}
```

The Griddy API accepts the claim as either a list of strings or a
single space-delimited string.

## Lifecycle

Clerk session tokens have a short TTL (~60s by default). The browser
SDKs handle refresh automatically; you just call `getToken()` and get
a current one. Server-side users of the Backend API should mint fresh
tokens per request rather than caching.

When a user signs out of your frontend, their session is invalidated on
Clerk's side and any tokens previously issued from it become unusable.

## Troubleshooting

See [Errors & Troubleshooting](errors.md) for full coverage. The most
common JWT-specific issues:

- `Token has expired` — Clerk session tokens are ~60s; mint a fresh one.
- `Invalid audience.` — your `aud` doesn't match the API's expected
  value. Check what audience your dashboard's session token is issuing
  with.
- `Invalid authorized party.` — backend-API-minted tokens have no `azp`
  claim. Either don't configure authorized parties for that environment
  or use a frontend-issued token.
