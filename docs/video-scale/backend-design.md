# v1.5 video backend — design sketch (TGF-338)

_Spike deliverable 3 of 4. Companion to [comparison.md](./comparison.md),
[migration-plan.md](./migration-plan.md), and
[ADR-0009](https://github.com/Thistle-Grow-Software/griddy-web-portal/blob/main/docs/adr/0009-v15-video-delivery-scale.md)._

A design sketch — not an implementation spec — for the v1.5 backend: the
transcoding/ingestion pipeline, the R2 storage layout, signed-URL/token
issuance at scale, and the clip-manifest service that unblocks TGF-339. It
answers ticket questions #3, #6, and #7 and feeds the follow-up stories.

Everything here **extends** the v1 pieces (Django playback API TGF-360, Worker
gateway TGF-361, batch packager TGF-362) rather than replacing them.

## 1. Ingestion / transcoding pipeline (#3)

### Shape: one-time batch, not a persistent service

The catalog is **static history** (TGF-337). So packaging is a **batch backfill**
that runs once per source asset and then never again — not a standing pipeline.
A persistent, autoscaling transcode service is only warranted once
user-generated uploads land (out of scope for v1.5; see ADR-0009). The same code
path is reused for the occasional new archival acquisition, invoked manually.

```
VideoAsset (GAM holdings)                      R2: griddy-video bucket
      │  source MP4 on /mnt or S3                       │
      ▼                                                 │
 [ probe ]  ffprobe → codecs, bitrate, resolution       │
      │                                                 │
      ├─ conforming (99%, H.264/AAC) ─┐                 │
      │                               ▼                 │
      │                        [ ABR transcode ]        │
      │                  ffmpeg → 240/480/720/1080       │
      │                  (cap rungs at source res)       │
      │                               │                 │
      └─ non-conforming (~10 files) ──┤                 │
            VP9/AV1/HEVC/Opus/AC-3    │                 │
            transcode to H.264/AAC    │                 │
                                      ▼                 │
                              [ package: CMAF/fMP4 ]     │
                          Shaka Packager / Bento4 mp4hls │
                          → master.m3u8 + per-rung        │
                            media playlists + init/seg    │
                                      │                  ▼
                                      └──── upload ──► games/{id}/...
                                            (idempotent put,
                                             content-type set)
                                      │
                                      ▼
                          write PackagedRendition rows (GAM)
                          status, ladder, checksum, segment count
```

### Bitrate ladder

A standard 4-rung ladder, each rung **capped at the source resolution** (43.9%
of the catalog is 720p, 39.7% is 480p — most files do not warrant a 1080p rung):

| Rung | Resolution | ~Bitrate | Produced when source ≥ |
| --- | --- | --- | --- |
| 1080p | 1920×1080 | ~5 Mbps | 1080p |
| 720p | 1280×720 | ~2.8 Mbps | 720p |
| 480p | 854×480 | ~1.4 Mbps | 480p |
| 240p | 426×240 | ~0.4 Mbps | always |

Segment duration stays at the v1 **~6 s** target so existing segments and the
gate behavior are unchanged. CMAF/fMP4 with a shared `init.mp4` per rung.

### Where it runs

One-time batch → cheapest correct answer is **own compute** (a workstation, a
spot VM, or Fargate spot), writing straight to R2. Projected one-time cost
~$300–500 (see comparison.md). No standing infrastructure. A new Django
management command — `package_game --ladder abr` — generalizes the v1
`poc_load_game`/TGF-362 packager from single-rendition `-c copy` to the ladder
above, reusing its R2 uploader and measurement output.

### Idempotency & provenance

- Uploads are keyed by deterministic object path (below), so re-running is safe.
- Each packaged ladder records a `PackagedRendition` row in GAM linked to the
  `VideoAsset` (status, rung set, per-object SHA-256, segment count, ffmpeg
  version) so a packaging run is auditable and re-derivable.

## 2. Storage layout (R2)

One bucket (`griddy-video`, as in v1). ABR adds a rung dimension under each
game; the master manifest and the v1 single-rendition path stay valid so v1
playback URLs never break during migration (see migration-plan.md).

```
games/{game_id}/
  master.m3u8              # multivariant: lists all rungs (NEW: was single-rung in v1)
  audio/
    init.mp4
    seg_00000.m4s …
  v1080/
    init.mp4
    seg_00000.m4s …
  v720/  v480/  v240/      # same shape per rung
  master.v1.m3u8           # retained: the v1 single-rendition manifest (migration safety)
```

- Storage estimate: ~2–2.5× source for the ladder + retained originals → ~6–7.5
  TB → ~$100–115/mo on R2, egress $0 (comparison.md).
- Originals are **retained** (cold) so any rung can be re-derived without
  re-acquiring the source.

## 3. Access control & signed-URL issuance at scale (#7)

v1 mints a **per-game** token (Django) that the Worker swaps for a **per-game,
path-scoped signed cookie**. That is correct for single-game playback and is
kept. v1.5 adds a second pattern for the cross-catalog clip experience, where a
session touches many games and minting one cookie per game is too chatty.

### Two token scopes

| Scope | Use | Claim shape | Cookie path |
| --- | --- | --- | --- |
| **Game** (v1, kept) | Watch one full game | `{sub, gid, iss, aud, exp}` | `/games/{gid}/` |
| **Session** (v1.5, new) | Browse/clip across the catalog | `{sub, ent, iss, aud, exp}` where `ent` = entitlement (e.g. allowed leagues / subscription tier) | `/` (entitlement checked per request) |

The Worker's `authorize()` already validates HS256 claims and supports a missing
`gid` (it falls back to `scopedTo() === true`). The v1.5 change is additive:
when a credential carries `ent` instead of `gid`, the Worker checks the
requested game against the entitlement claim rather than a single `gid` match.
Entitlement stays **single-sourced in Django** (against Clerk identity, per
ADR-0006) — the Worker still only verifies a token Django minted; it gains an
entitlement check, not an identity surface.

```
Portal ──Clerk JWT──► Django  GET /api/playback/session
                        │  check subscription/entitlement (Clerk → coach/team)
                        ▼
                 mint session token {sub, ent=[NFL,UFL], exp=+1h}
Portal ◄──────────────── token ──────────────┘
   │  player loads any games/{id}/master.m3u8?t=<session token>
   ▼
Worker  verify token → entitlement allows {id}? → set session cookie (Path=/) → stream
```

- **Lifetimes.** Game token: minutes (one-shot, swapped immediately for the
  cookie). Session cookie: a few hours (must outlive a multi-game clip session),
  silently re-minted by the portal on expiry — same rationale as the v1 ADR's
  "credential must outlive a segment fetch".
- **Per-coach subscription gating** lives entirely in the `ent` claim: Django
  computes it from the authenticated user's subscription; the Worker enforces it
  per request. Revoking access = not minting the next token (≤ cookie TTL to
  take effect).
- **CORS** is unchanged from v1 (explicit credentialed origins, `GET, HEAD`,
  `Range`, range headers exposed).

## 4. Clip-manifest service (#6, unblocks TGF-339)

The headline v1.5 feature plays **arbitrary time ranges across the catalog**.
Three options were on the table; the design picks the third.

| Option | Storage | Compute | UX | Verdict |
| --- | --- | --- | --- | --- |
| Server-side concat → new HLS asset | New per clip (blows up) | Re-mux per clip | Seamless | Rejected — cost |
| Client-side chained playback + seek jumps | None | None | Visible seams | Rejected — UX |
| **Synthesized clip manifest over stored segments** | **None** | Generate a playlist (cheap) | Seamless within a rung; ~6 s edge granularity | **Chosen** |

### How it works

A clip is identified by `(game_id, start, end)`. The service emits an **HLS
media playlist** that references the **already-stored ABR segments** overlapping
`[start, end]`:

```
#EXTM3U
#EXT-X-VERSION:7
#EXT-X-MAP:URI="/games/2025001/v720/init.mp4"
#EXT-X-START:TIME-OFFSET=0
#EXTINF:6.0,
/games/2025001/v720/seg_00042.m4s     # first segment covering `start`
…                                      # whole segments in range
#EXTINF:6.0,
/games/2025001/v720/seg_00058.m4s     # last segment covering `end`
#EXT-X-ENDLIST
```

- **No new storage, no re-encode** — the clip reuses the same segment objects the
  full-game stream serves; only a small text manifest is generated.
- **Granularity:** v1.5 ships at segment (~6 s) edges, with `EXT-X-START` for the
  in-point. Frame-accurate trimming of the two boundary segments (a tiny
  on-the-fly remux of ≤2 segments) is a documented later refinement, not a v1.5
  blocker.
- **Where it runs:** the manifest is generated where the segment timing is
  known. Two viable homes — (a) **Django** `GET /api/games/{id}/clip.m3u8?start=&end=`
  using packaging metadata, or (b) the **Worker**, computing segment indices from
  the media playlist it already serves. Recommendation: **Django generates,
  Worker gates** — it keeps timing logic next to the `PackagedRendition`
  metadata and leaves the Worker a pure auth+stream gate. The clip manifest is
  fetched under the same session token/cookie as any other object.
- **Cross-catalog playlists** (a filtered set of clips from many games, the
  NFL-Pro-style feature) become a **client-side ordered list of per-clip
  manifests**, each gated by the one session token — the player loads them in
  sequence. Seams fall on clip boundaries (expected for a highlight reel), not
  mid-play.
- **ABR is free here:** because clip manifests point at the multivariant
  segments, clips get adaptive bitrate with no extra work.

### PBP sync (TGF-339 sibling)

Play-by-play sync needs a **game-clock → media-time** mapping. That mapping is a
data concern (a per-game offset table relating PBP timestamps to media
position), independent of delivery; it is noted here as a consumer of the same
clip endpoint and is scoped in its own story rather than designed in this spike.

## 5. What stays the same

- The Worker gateway, its HS256 verify, signed-cookie mechanics, Range/scrubbing
  handling, and CORS — extended (session scope, ABR paths), not rewritten.
- The Django playback API (TGF-360) — gains a session endpoint and a clip
  endpoint alongside the existing per-game one.
- The player (vidstack/hls.js) — consumes multivariant manifests and clip
  manifests with **no change** (ADR-0008 anticipated this).
- Local-first development — the whole stack still runs under `wrangler dev` +
  Miniflare R2 with zero cloud spend; ABR packaging and clip manifests are
  exercised locally exactly as the v1 PoC was.

## Open questions for implementation stories

1. Exact ladder bitrates/codec profiles — tune against a sample of real games.
2. Boundary-segment trimming: ship segment-granularity v1.5, or include the
   ≤2-segment remux from the start? (Recommend: defer.)
3. Session-token entitlement shape — leagues vs teams vs subscription tier —
   needs the subscription model (not yet built) to firm up.
4. Transcode host — workstation vs Fargate spot — a cost/convenience call made
   at backfill time.
