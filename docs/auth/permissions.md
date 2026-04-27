# Permission Catalog

This page is the canonical reference for the permissions the Griddy API
recognizes, the convention used to name them, and how DRF enforces them.
Once SDK clients depend on these strings they become a public contract —
treat additions as cheap and removals as breaking.

## Naming convention: `resource:verb`

Every permission is named `<resource>:<verb>` (e.g. `catalog:read`).

**Resource first, verb second.** Three reasons:

1. **Sorts and globs naturally.** Listing a token's permissions groups them
   by data domain, and future wildcard support (`catalog:*`) reads cleanly.
2. **Verbs grow more often than resources.** New verbs (`export`, `archive`,
   `restore`) tend to appear inside an existing domain, so resource-first
   keeps related entries adjacent.
3. **Colon over dot.** The colon separator matches OAuth scope conventions
   used by Stripe, Slack, GitHub, and others — easier for SDK consumers to
   recognize as a permission rather than a method path.

The other two conventions we considered:

- **`verb:resource` (GitHub-style, e.g. `read:catalog`).** Rejected because
  it groups all read-only access together at the cost of splitting each
  resource across multiple list positions.
- **`resource.verb` (Google-style, e.g. `catalog.read`).** Rejected because
  the dot is also our module-path separator and JSON access notation; using
  it for permissions invites visual collisions.

## Catalog

The initial set is deliberately small. Two domains, two verbs each:

| Permission | Grants | Enforced on |
|---|---|---|
| `catalog:read` | List/retrieve catalog resources (leagues, seasons, games, teams, venues, org units, affiliations, standings, plays, boxscores, drives, replays, completeness records). | `LeagueViewSet`, `SeasonViewSet`, `FranchiseViewSet`, `TeamViewSet`, `OrgUnitViewSet`, `TeamAffiliationViewSet`, `VenueViewSet`, `TeamVenueOccupancyViewSet`, `GameViewSet`, `GameCompletenessViewSet`, `TeamStandingsSnapshotViewSet`, `GamePlayViewSet`, `PlayStatViewSet`, all nested boxscore viewsets. |
| `catalog:write` | Create/update/delete the same resources. | Same viewsets (write actions). |
| `holdings:read` | List/retrieve holdings resources (sources, acquisitions, video assets, tags, asset tags). | `SourceViewSet`, `AcquisitionViewSet`, `VideoAssetViewSet`, `TagViewSet`, `AssetTagViewSet`. |
| `holdings:write` | Create/update/delete holdings resources. | Same viewsets (write actions). |

The catalog/holdings split mirrors the project's two-domain data model
described in `archive/CLAUDE.md`. Holdings tend to be more sensitive
(internal acquisition records, file paths) than catalog data, so we want to
gate them with separate permissions even when read-only.

## Enforcement

DRF reads the permission set from the validated JWT's `permissions` claim
(populated by Clerk — see "JWT template" below). Every viewset that should
be gated uses one of two mixins from `gam.auth.permissions`:

```python
from gam.auth.permissions import CatalogPermissionMixin, HoldingsPermissionMixin

class LeagueViewSet(CatalogPermissionMixin, ...):
    ...

class SourceViewSet(HoldingsPermissionMixin, ...):
    ...
```

Each mixin sets `permission_classes = [HasAPIPermission]` and
`required_permissions` to the appropriate action map.
:class:`HasAPIPermission` looks up the current DRF action (`list`,
`retrieve`, `create`, `update`, `partial_update`, `destroy`) in the map; if
no entry matches, it falls back to the `default` key (used for custom
`@action` methods).

Override on a single viewset when needed:

```python
class TeamViewSet(CatalogPermissionMixin, ...):
    required_permissions = {
        **CATALOG_PERMISSIONS,
        "merge": [Permissions.CATALOG_WRITE],  # custom @action
    }
```

A view with no `required_permissions` is treated as "no permission
required" — `HasAPIPermission` returns `True` and other permission classes
(if any) decide the outcome.

## Token format

`HasAPIPermission` accepts the `permissions` claim in either form:

```json
{ "permissions": ["catalog:read", "holdings:read"] }
```

```json
{ "permissions": "catalog:read holdings:read" }
```

The space-delimited string form mirrors how OAuth `scope` is serialized,
making it convenient for IdPs that can only emit string claims.

## JWT template (Clerk)

The `permissions` claim is **not** populated automatically by Clerk; it
must be added to the JWT template in the Clerk dashboard. Suggested
template snippet (read from organization role + user public metadata):

```json
{
  "permissions": "{{user.public_metadata.permissions}}"
}
```

Or, if using Clerk Organizations:

```json
{
  "permissions": "{{org_membership.permissions}}"
}
```

Until the template is updated, all gated endpoints will return `403` for
real Clerk tokens — the local-dev harness (`scripts/local_jwks_server.py`)
and the `mint_clerk_token.py` script can include arbitrary claims for
testing.

## Adding a new permission

1. Add a constant to :class:`gam.auth.permissions.Permissions`.
2. Reference it from the appropriate action map (or create a new mixin).
3. Document it in the table above with what it grants and where it is
   enforced.
4. If the permission is meant to be granted by default, update the Clerk
   JWT template / user metadata so existing tokens carry it.

Removing a permission is a breaking change for SDK clients — prefer
deprecating (stop enforcing it, leave it in tokens) over deleting.

## Out of scope (for now)

Per-object permissions (e.g. "user X can edit asset Y but not Z") are
intentionally **not** implemented in this iteration. We expect access
patterns to clarify before designing object-level rules; revisit once
SDK consumers and concrete tenancy requirements are in hand.
