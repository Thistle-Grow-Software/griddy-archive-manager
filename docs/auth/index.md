# API Authentication

The Griddy API supports two authentication paths. Pick the one that
matches how you're calling it.

## Which path do I use?

| You are... | Use | Why |
|---|---|---|
| Building a browser app where end users sign in | **JWT (Clerk session token)** | Each request is attributed to a real user; tokens are short-lived and rotated automatically by Clerk. |
| Calling the API from your own backend, a CI job, a notebook, or any unattended script | **API key** | No browser, no end user — your service is the account holder. Long-lived, revocable, scoped credentials. |
| Building an SDK that runs in someone else's backend | **API key** | Same as above; ship without a browser dependency. |
| Acting as a third-party app on behalf of a Griddy user | (not yet supported) | OAuth/PKCE flow is on the roadmap. |

If you're unsure, default to **API key** — it's the simpler shape and most
developer integrations end up there.

## At a glance

Both paths use the same header:

```
Authorization: Bearer <token>
```

What differs is the token format and how you obtain it.

=== "API key"

    Token format: `grd_live_<48 hex chars>` (or `grd_test_…` for test keys).

    ```bash
    curl -H "Authorization: Bearer grd_live_a1b2c3..." \
         https://api.griddy.test/api/v1/leagues/
    ```

    Issued via the developer dashboard or the `/api/v1/api-keys/`
    endpoint. Once issued, the plaintext is **shown exactly once** —
    save it then or revoke and re-issue.

    See [API Keys](api-keys.md) for the full guide.

=== "JWT (Clerk session)"

    Token format: a standard RS256-signed JSON Web Token.

    ```bash
    curl -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
         https://api.griddy.test/api/v1/leagues/
    ```

    Obtained client-side from Clerk's React/JS SDK after the user signs in:

    ```typescript
    import { useAuth } from "@clerk/clerk-react";

    const { getToken } = useAuth();
    const token = await getToken();
    ```

    See [JWT Authentication](jwt.md) for the full guide.

## What both paths share

* **Same permission catalog.** Tokens carry a list of permissions like
  `catalog:read` and `holdings:write`. Whether they live in the JWT's
  `permissions` claim or on the API key's `scopes` field, the strings —
  and the endpoints they gate — are identical. See
  [Permissions](permissions.md).

* **Same error semantics.** A `401` means we couldn't authenticate the
  request at all. A `403` means we authenticated you but you lack the
  required permission for that endpoint. See
  [Errors & Troubleshooting](errors.md).

* **Coexistence on a single endpoint.** Every endpoint accepts either
  bearer-token shape; the server picks the right verifier based on the
  token's prefix. No need to maintain separate API surfaces for
  human-driven vs. machine-driven traffic.

## Quickstart links

- New to the API? Start with the [SDK quickstart for Python](https://docs.thistlegrow.com/griddy-sdk-python/) or [TypeScript](https://docs.thistlegrow.com/griddy-sdk-typescript/).
- Already have a token? Jump to [Permissions](permissions.md) to scope your access correctly.
- Hitting `401` or `403`? See [Errors & Troubleshooting](errors.md).
