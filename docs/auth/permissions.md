# Permissions

Authenticated requests are gated by **permissions** — short string
identifiers that say "this token may perform this kind of action." Both
auth paths use the same catalog: JWTs carry permissions in the
`permissions` claim, API keys carry them in the `scopes` field, and the
strings — and the endpoints they unlock — are identical either way.

These strings are a **stable contract**. Once SDK consumers depend on
them, removals are breaking changes; additions are cheap.

## The catalog

Two domains, two verbs each. Four permissions total.

| Permission | Grants | Endpoints |
|---|---|---|
| `catalog:read` | Read catalog resources — leagues, seasons, games, teams, venues, organizational hierarchy, affiliations, standings, plays, boxscores, drives, replays, completeness records. | `GET` on every catalog endpoint. |
| `catalog:write` | Create, update, and delete the same resources. | `POST` / `PUT` / `PATCH` / `DELETE` on every catalog endpoint. |
| `holdings:read` | Read holdings resources — sources, acquisitions, video assets, tags, asset tags. | `GET` on every holdings endpoint. |
| `holdings:write` | Create, update, and delete the same resources. | `POST` / `PUT` / `PATCH` / `DELETE` on every holdings endpoint. |

**Catalog** describes football data that exists in the world (games,
teams, venues). **Holdings** describes what you own (video files,
acquisition records). Holdings tend to be more sensitive — file paths,
purchase metadata — so they're gated separately even when read-only.

If your token has only `catalog:read`, the holdings endpoints return
`403` regardless of HTTP method, and vice versa. Read-only access
doesn't grant write — even within a single domain — so a token with
`catalog:read` can list leagues but cannot create one.

## Naming convention

Every permission is named `<resource>:<verb>`. The resource comes
first, the verb second, and the separator is a colon.

If you're integrating from elsewhere, expect this convention to extend
predictably. New verbs (`export`, `archive`, `restore`) will appear
inside existing domains. New resources will introduce new prefixes.
Wildcards (`catalog:*`) are not supported today but the format is set
up for them.

## Token format

The Griddy API accepts two equivalent shapes for the permissions list:

```json
{ "permissions": ["catalog:read", "holdings:read"] }
```

```json
{ "permissions": "catalog:read holdings:read" }
```

The space-delimited string form mirrors how OAuth `scope` is serialized
on the wire, making it convenient for IdPs that can only emit string
claims. Use whichever your client emits naturally; both are accepted.

## Configuring permissions on tokens

### For JWTs (Clerk)

Add the `permissions` claim under **Sessions → Customize session
token** in the Clerk dashboard. A common pattern reads from user public
metadata:

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

See [JWT Authentication](jwt.md) for full details, including why the
session token (not a JWT template) is the right place for this.

### For API keys

Specify scopes at issuance:

```json
POST /api/v1/api-keys/
{
  "name": "Read-only dashboard",
  "scopes": ["catalog:read"]
}
```

Once issued, scopes cannot be changed. Issue a new key with the
desired scopes and revoke the old one.

## What "missing permission" looks like

If a token authenticates successfully but lacks the required
permission, the API returns:

```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{"detail": "Token is missing one or more required permissions."}
```

A `403` always means *authenticated, but not authorized*. If you're
seeing it on every request and you expect to have access, check that:

1. The endpoint actually requires what you think it does — write
   endpoints need `*:write`, not `*:read`.
2. Your token actually carries the claim you expect — decode it at
   [jwt.io](https://jwt.io) (for JWTs) or list your API keys to see
   their scopes.
3. The catalog/holdings split is intentional — `catalog:read` does not
   grant access to `/api/v1/sources/`.

See [Errors & Troubleshooting](errors.md) for the full debugging walkthrough.

## What's not in the catalog (yet)

Per-object permissions — "user X can edit asset Y but not asset Z" —
are intentionally not implemented. The current model is "if you have
the verb, you have it everywhere within the domain." Revisit when
multi-tenancy and per-row sharing become real requirements.
