# Video delivery at scale (v1.5) — TGF-338 spike

Investigation and design output for **TGF-338 — _Spike: Video delivery
infrastructure at scale (v1.5 prerequisite)_**. Where the v1 spike (TGF-337,
`docs/video-poc/`) answered "how do we serve the existing film at all", this
spike answers "how do we serve it at scale, with ABR, analytics, and
cross-catalog clip playback, without re-platforming".

The headline decision — **extend the self-hosted R2 + Worker stack rather than
move to Mux or Cloudflare Stream** — is recorded as an ADR in the portal repo
(ADRs live there, next to ADR-0008):
[ADR-0009 — v1.5 video delivery at scale](https://github.com/Thistle-Grow-Software/griddy-web-portal/blob/main/docs/adr/0009-v15-video-delivery-scale.md).

## Documents

| Deliverable | Doc | Answers ticket Q |
| --- | --- | --- |
| Build-vs-buy comparison (cost, DX, feature fit, ops) | [comparison.md](./comparison.md) | #1, #2, #4, #5 |
| Migration plan v1 → v1.5 | [migration-plan.md](./migration-plan.md) | #8 |
| Backend design sketch (ingest, storage, signed URLs, clips) | [backend-design.md](./backend-design.md) | #3, #6, #7 |
| ADR (v1.5 direction + rationale) | [ADR-0009 ↗](https://github.com/Thistle-Grow-Software/griddy-web-portal/blob/main/docs/adr/0009-v15-video-delivery-scale.md) | decision |

Follow-up implementation epic and stories are filed in Jira and linked from
TGF-338.

## One-paragraph summary

For a large, static, already-HLS-friendly catalog served with free egress from
Cloudflare, self-hosted R2 + Worker delivery stays flat at ~$120/mo at every
viewing volume, while Mux, Cloudflare Stream, and AWS CloudFront all start higher
and grow with delivered minutes — there is no volume at which they win. So v1.5
**extends** v1: a one-time ABR transcode backfill, a session-scoped access token
for cross-catalog browsing, a synthesized **clip-manifest service** that plays
arbitrary time ranges over the already-stored segments with no re-encode and no
new storage (unblocking TGF-339), and **Mux Data** bolted on for player QoS.
Managed **Mux Video** is kept as the documented escape hatch for the day
user-generated uploads create a persistent transcode pipeline.
