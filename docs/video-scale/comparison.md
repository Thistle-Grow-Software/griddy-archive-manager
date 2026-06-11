# Video delivery at scale — build vs buy (TGF-338)

_Spike deliverable 1 of 4. Companion to [ADR-0009](https://github.com/Thistle-Grow-Software/griddy-web-portal/blob/main/docs/adr/0009-v15-video-delivery-scale.md) (the decision), [migration-plan.md](./migration-plan.md), and [backend-design.md](./backend-design.md)._

This document compares the four delivery stacks named in TGF-338 — **Mux**,
**Cloudflare Stream**, **self-hosted R2 + Worker** (the v1 stack, extended),
and **self-hosted AWS (S3 + CloudFront + MediaConvert)** — on cost, developer
experience, feature fit, and operational burden, and identifies the crossover
points. It answers ticket questions #1, #2, #4, and #5.

## TL;DR

For **this** catalog — large (~2.95 TiB), static history, already 99% H.264/AAC,
served from inside the Cloudflare ecosystem with free egress — **extending the
self-hosted R2 + Worker stack wins at every viewing volume.** Managed services
(Mux, CF Stream) and AWS CloudFront all start at a higher fixed cost and grow
with delivered minutes; R2 stays flat at roughly **$120/mo** because egress is
free and storage is cheap. The managed services' value (turnkey transcoding,
bundled analytics) does not offset a 3–5× monthly premium for a catalog that
transcodes **once** and never churns.

The one piece worth buying is **player analytics** (Mux Data), which is sold
decoupled from delivery, has a free tier, and works with the existing
hls.js/vidstack player — so we get QoS metrics without the delivery premium.

## Catalog sizing assumptions

All figures are projected to ~1.5× accuracy — enough to separate "$100/mo" from
"$1,000/mo", per the same bar the v1 cost model used.

| Input | Value | Basis |
| --- | --- | --- |
| Catalog size on disk | 2.95 TiB (~3,242 GB) | `video_stats.md` (TGF-337) |
| Games | ~1,204 | TGF-337 catalog report |
| Catalog content-minutes | **~120,000 min (~2,000 hr)** | 3,242 GB ÷ ~27 MB/min mean (bitrate centroid ~2–3 Mbps, weighted to the 0.5–1 Mbps SD majority); ~1.5× estimate |
| Mean watched minutes / stream | ~30 min | PoC condensed game ran 32 min; users watch portions |
| ABR ladder storage multiple | ~2–2.5× source | 240/480/720/1080 renditions vs single remux (v1 was ~1×) |

**Viewing-volume scenarios** (carried from the v1 cost model, now expressed in
delivered minutes at ~30 min/stream):

| Scenario | Streams/mo | Delivered min/mo |
| --- | --- | --- |
| Pilot | 100 | 3,000 |
| Small | 1,000 | 30,000 |
| Active | 10,000 | 300,000 |
| Heavy | 100,000 | 3,000,000 |

## Published pricing used (USD, early 2026)

Prices drift; treat as order-of-magnitude. Sources are each vendor's public
pricing page as of the spike.

| Stack | Storage | Delivery / egress | Transcode | Notes |
| --- | --- | --- | --- | --- |
| **R2 + Worker** | $0.015/GB-mo | **$0** egress | one-time batch (own compute) | Workers $5/mo + $0.30/M reqs >10M; Class B reads $0.36/M |
| **CF Stream** | $5 / 1,000 min stored-mo | $1 / 1,000 min delivered | included | Bills on source minutes; renditions managed for you |
| **Mux Video** | ~$0.003/min-mo (encoded) | ~$0.001/min delivered | ~$0.0072/min one-time encode | Mux Data analytics sold separately (free < 100k views/mo) |
| **AWS** | S3 $0.023/GB-mo | CloudFront ~$0.085/GB egress | MediaConvert ~$0.0075–0.015/min | Egress is the dominant term |

## Projected monthly cost

ABR-ladder storage is taken as ~6–7.5 TB for the self-hosted stacks (renditions
+ retained originals). Delivered GB assumes ~22.5 MB/min (~3 Mbps avg
rendition).

| Scenario | R2 + Worker | CF Stream | Mux Video | AWS (S3+CF) |
| --- | --- | --- | --- | --- |
| **Pilot** (3k min) | **~$120** | ~$603 | ~$363 | ~$146 |
| **Small** (30k min) | **~$120** | ~$630 | ~$390 | ~$197 |
| **Active** (300k min) | **~$121** | ~$900 | ~$660 | ~$714 |
| **Heavy** (3M min) | **~$145** | ~$3,600 | ~$3,360 | ~$5,878 |
| One-time transcode | ~$300–500 | included | ~$864 | ~$900–1,800 |
| Fixed storage floor | ~$115/mo | ~$600/mo | ~$360/mo | ~$140/mo |

### Reading the table

- **R2 is flat.** Storage dominates and is fixed; reads/Workers stay in the
  single-to-low-double digits even at 100k streams because R2 reads are
  $0.36/M and egress is free. This is the same dynamic the v1 cost model found,
  carried forward with a larger (ABR) storage base.
- **CF Stream and Mux are storage-bound at low volume.** Their per-stored-minute
  pricing puts the floor at $360–600/mo *before anyone watches anything* — 3–5×
  the entire R2 bill. They only approach parity-of-growth at Heavy volume, and
  even then they are 20–30× more expensive in absolute terms.
- **AWS is cheapest among the alternatives at Pilot/Small but the worst at
  scale** — CloudFront egress grows linearly with delivered minutes and crosses
  R2 between Small and Active, reaching ~40× R2 at Heavy.

### Crossover points

- There is **no viewing volume at which any alternative beats R2** for this
  catalog. R2's storage-only floor (~$115/mo) sits *below* the managed services'
  storage-only floors ($360–600/mo), and its marginal delivery cost is ~$0.
- AWS's *fixed* cost (~$140/mo) is within ~20% of R2's, but its *marginal* cost
  (egress) makes the total cross above R2 at roughly **40,000 delivered min/mo
  (~Small+)** and diverge sharply after.
- The managed services would only win if the catalog were **small and churning**
  (storage cheap, transcoding frequent) — the opposite of Griddy's static
  archive — or if their bundled features were independently worth the premium
  (addressed below).

## Developer experience

| Stack | DX | Verdict |
| --- | --- | --- |
| **Mux** | Best in class. Upload → playback URL in one API call; dashboard, signed playback, Data analytics, clipping API all turnkey. | Highest, but we have already built the equivalent gate/packaging for v1. |
| **CF Stream** | Strong; single API, native to our Cloudflare account, Stream Player included. | High; least-effort *managed* option given we are already on Cloudflare. |
| **R2 + Worker** | We own it. v1 already shipped the Worker gate, signed cookie, CORS, and `-c copy` packaging. Marginal DX cost for v1.5 is the ABR ladder + clip service. | Moderate up-front, zero vendor lock-in. The hard parts are done. |
| **AWS** | Heaviest. MediaConvert job templates, CloudFront signed cookies, OAC, S3 lifecycle — most moving parts. | Lowest; only justified if live streaming (MediaLive) were on the roadmap. It is not. |

## Feature fit (v1.5 needs)

| Need (ticket) | Mux | CF Stream | R2 + Worker | AWS |
| --- | --- | --- | --- | --- |
| **ABR ladders** (240/480/720/1080) | Automatic | Automatic | Batch transcode (one-time); player already consumes multi-rendition manifests (ADR-0008) | MediaConvert |
| **Clip playback across catalog** (TGF-339) | Clipping API (per-asset; cross-asset is manual) | Clipping (per-video) | **Synthesized clip-manifest** over stored segments — no re-encode, no new storage (see backend-design.md) | Manual (packager + manifest gen) |
| **Analytics / QoS** (#5) | Mux Data (best) | Stream analytics (good) | Build, or bolt on **Mux Data standalone** | Build (CloudFront logs + own pipeline) |
| **Signed access at scale** (#7) | Signed playback tokens | Signed URLs / tokens | Existing Django-token → Worker → signed-cookie; extend to session/entitlement scope | CloudFront signed cookies |
| **DRM** (#4) | Add-on (Widevine/FairPlay/PlayReady) | Add-on | Not built | SPEKE + DRM vendor |

**Clip generation (#6)** is the deciding feature for TGF-339 and the one place
self-hosting is *better*, not just cheaper: because we own the segment store, a
clip is a **generated HLS media playlist** that references the existing ABR
segments overlapping `[start, end]` — zero new storage, zero re-encode, segment
(~6 s) granularity for v1.5 with optional boundary trimming later. The managed
clipping APIs are per-asset and would force either re-rendering each clip
(storage/compute blow-up, the "server-side concat" anti-pattern the ticket
flags) or paying to store derived clips. Detailed in
[backend-design.md](./backend-design.md).

## DRM (#4) — decision: defer

The v1.5 catalog is owned/coaching and archival football film, not licensed
broadcast content. The signed-cookie gate (entitlement enforced in Django,
verified per-request at the Worker) is the appropriate control. **DRM is
deferred.** Revisit only if Griddy licenses third-party broadcast footage whose
rights contract mandates it — at which point Mux/CF Stream's DRM add-on becomes a
reason to put *that subset* on a managed origin, not a reason to re-platform the
whole catalog.

## Analytics & QoS (#5) — bar for v1.5

Track per playback session: **startup time, rebuffer ratio, completion rate,
fatal error rate**, plus rendition/bandwidth distribution. Self-hosting delivery
does not mean building analytics: **Mux Data** is sold standalone, integrates
with hls.js/vidstack via a small SDK, and is free under ~100k monthly views —
covering Pilot through Active for ~$0. This is the recommended way to hit the QoS
bar without taking on the delivery premium.

## Ops burden

| Stack | Ongoing ops |
| --- | --- |
| **R2 + Worker** | A Worker deploy + an R2 bucket (both already in v1). Batch transcode is one-time for a static catalog. Lowest *ongoing* burden precisely because nothing recurs. |
| **CF Stream / Mux** | Near-zero ops, but a recurring bill and a vendor dependency for the core product surface. |
| **AWS** | Highest: MediaConvert templates, CloudFront distributions/invalidation, signed-cookie key rotation, S3 lifecycle. |

The ops argument for "buy" is strongest when transcoding is **continuous** —
i.e. once user-generated uploads land. That is out of scope for v1.5 (the
catalog is fixed) but is the documented trigger to revisit (see ADR-0009).

## Recommendation

**Extend the self-hosted R2 + Worker stack for v1.5.** Add a one-time ABR
transcode pass, build the clip-manifest service in-house, and adopt **Mux Data**
for player QoS. Keep **Mux Video** documented as the escape hatch for the day
user uploads create a persistent transcode pipeline. Rationale and consequences
are recorded in [ADR-0009](https://github.com/Thistle-Grow-Software/griddy-web-portal/blob/main/docs/adr/0009-v15-video-delivery-scale.md).
