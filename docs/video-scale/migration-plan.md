# Migration plan — v1 → v1.5 video delivery (TGF-338)

_Spike deliverable 2 of 4. Companion to [comparison.md](./comparison.md),
[backend-design.md](./backend-design.md), and
[ADR-0009](https://github.com/Thistle-Grow-Software/griddy-web-portal/blob/main/docs/adr/0009-v15-video-delivery-scale.md)._

Answers ticket question #8: how do we move from the v1 delivery stack (TGF-337 /
ADR-0008) to v1.5 **without breaking existing users**? Because the v1.5 decision
is to *extend* the v1 stack rather than re-platform onto a managed service, this
is an additive, zero-downtime migration — no data leaves Cloudflare, no URLs are
invalidated, and every step is independently reversible.

## What v1 is (the starting point)

| Piece | Where | v1 behavior |
| --- | --- | --- |
| Storage | R2 `griddy-video` | One **single-rendition** `-c copy` remux per game: `games/{id}/master.m3u8` + `init.mp4` + `seg_*.m4s` |
| Gate | Worker (TGF-361) | Validates a **per-game** HS256 token → sets a per-game path-scoped signed cookie → streams objects |
| API | Django (TGF-360) | `GET /api/games/{id}/playback` → manifest URL + per-game token |
| Player | vidstack/hls.js (TGF-335) | Consumes the manifest; native HLS fallback on Safari |

Everything is single-vendor (Cloudflare) and local-first reproducible.

## Migration principle: additive, never destructive

The v1.5 storage layout (see backend-design.md) **adds** rung directories and a
multivariant `master.m3u8` while **retaining** the v1 single-rendition manifest
as `master.v1.m3u8`. The v1 token/cookie path keeps working unchanged. Nothing
is deleted or renamed, so a half-migrated catalog is fully playable: migrated
games serve ABR, not-yet-migrated games serve the v1 single rendition, and the
player handles both with no code change.

## Phases

### Phase 0 — Prerequisite: promote v1 to real Cloudflare

v1's PoC runs against local Miniflare R2. Production v1.5 needs a real R2 bucket
and the `video.griddy.football` Worker origin. This is the binding/config-only
promotion ADR-0008 anticipated (and that TGF-340's apex-domain work feeds). It is
a v1 deployment step, listed here because it gates everything below. **No v1.5
code depends on it being done first beyond having a real origin to package into.**

### Phase 1 — ABR packaging backfill (additive write)

- Generalize the TGF-362 packager to the 4-rung ladder (`package_game --ladder
  abr`).
- Run the one-time backfill, **writing new rung objects and a new multivariant
  `master.m3u8`** alongside the existing v1 objects. Copy the existing v1
  `master.m3u8` to `master.v1.m3u8` *before* overwriting it, so the old manifest
  survives.
- Idempotent and resumable (deterministic keys, `PackagedRendition` rows).
- **User impact: none.** No URL changes; the multivariant master is a superset.
  A game that has been backfilled simply gains lower/higher rungs the player can
  now choose between.

### Phase 2 — Session-scoped access (additive gate change)

- Add the Django **session endpoint** and the Worker **entitlement check** for
  the new `ent`-claim token (backend-design.md §3). The existing per-game token
  path is untouched — the Worker simply learns a second valid credential shape.
- **User impact: none.** Existing per-game playback continues on the old token;
  the session token is only exercised by new clip surfaces.

### Phase 3 — Clip-manifest service (new surface)

- Add `GET /api/games/{id}/clip.m3u8?start=&end=` (Django generates, Worker
  gates) over the already-stored ABR segments.
- Wire TGF-339's filtered-clip UI to it. This is **net-new functionality**, not a
  migration of anything existing.

### Phase 4 — Player QoS (additive instrumentation)

- Add the **Mux Data** SDK to the vidstack/hls.js player for startup time,
  rebuffer ratio, completion, and error metrics (comparison.md §Analytics).
- **User impact: none** beyond an analytics beacon.

### Phase 5 — Cutover & cleanup (deferred, optional)

Once the whole catalog is backfilled and ABR has been validated in production for
a soak period:

- Point any remaining direct references at the multivariant `master.m3u8`.
- Optionally retire `master.v1.m3u8` **only after** logs show no traffic to it.
  Until then it costs ~nothing (one small text object/game) and is the rollback
  anchor — there is no urgency to delete it.

## Rollback

Each phase reverts independently because nothing is destructive:

| If this breaks… | Roll back by… |
| --- | --- |
| ABR backfill (Phase 1) | Serving `master.v1.m3u8` (point the API/player back at the single rendition); rung objects are inert if unreferenced |
| Session gate (Phase 2) | Worker still accepts v1 per-game tokens; disable the session endpoint |
| Clip service (Phase 3) | Feature-flag the clip UI off; no impact on full-game playback |
| QoS (Phase 4) | Remove the analytics SDK init |

The v1 single-rendition fallback the ADR-0008 author kept ("serve raw
progressive MP4… it remains the fallback") still exists beneath all of this.

## Migration risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Backfill storage roughly triples footprint mid-run | Storage is ~$0.015/GB-mo and egress-free; even the doubled ~7 TB is ~$115/mo (comparison.md). Backfill in batches; monitor bucket size. |
| A re-encoded rung diverges from the source (quality regression) | `PackagedRendition` records per-object checksums + ffmpeg version; spot-check a sample per league against the source before retiring v1 manifests. |
| Session-token entitlement bug grants over-broad access | Entitlement is single-sourced in Django; default-deny in the Worker; short cookie TTL bounds blast radius; cover with the same Playwright auth-gate matrix the v1 PoC used (authorized 200, tampered/empty/wrong-scope 403). |
| Player picks a too-high rung on slow connections | hls.js ABR handles this automatically once the ladder exists; QoS metrics (Phase 4) confirm rebuffer ratio in the field. |

## Success criteria

- Every backfilled game plays ABR in Chrome, Firefox, and Safari with no change
  to its playback URL.
- A pre-migration v1 playback URL still plays after migration (no broken links).
- An unauthorized or wrong-entitlement request to any object returns 403 with no
  media (parity with the v1 gate guarantee).
- A clip request returns a playable manifest referencing only stored segments
  (no new media objects created).
- Catalog-wide R2 cost stays in the ~$100s/mo class projected in comparison.md.
