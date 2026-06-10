# Video delivery PoC runbook — one game, end-to-end (ADR-0008, TGF-363)

This is the reproducible proof that the ADR-0008 video-delivery design works
**end to end, entirely locally, with zero cloud spend**. It wires together the
three pieces built in TGF-360/361/362:

| Piece | Built in | Role in the chain |
| --- | --- | --- |
| Playback token (Django) | TGF-360 | Mints a short-lived, game-scoped HS256 token and the `…/games/{id}/master.m3u8?t=<token>` URL. |
| Packaging pipeline | TGF-362 | Remuxes a source game to CMAF/HLS (`master.m3u8` + `init.mp4` + `seg_*.m4s`). |
| Worker gateway | TGF-361 | Validates the token, sets a session cookie, and streams segments from R2 — 403 for anything unauthorized. |

The PoC packages a **real 2025 Week 1 game (MIA @ IND)** into the local
Miniflare R2 store and plays it in a real browser through the real Worker.

## The flow it proves (ADR-0008)

```
  Browser                     Worker (:8787)                 R2 (local Miniflare)
    │  GET /games/2025001/master.m3u8?t=<token>  │                      │
    │ ─────────────────────────────────────────► │  verify token        │
    │                                            │  (iss/aud/exp/gid)    │
    │  200 + Set-Cookie: griddy_video_session    │ ◄─ get master.m3u8 ── │
    │ ◄───────────────────────────────────────── │                      │
    │  GET …/init.mp4, …/seg_00000.m4s  (cookie) │                      │
    │ ─────────────────────────────────────────► │  verify cookie       │
    │  200 segment bytes (Range-capable)         │ ◄─ get object ─────── │
    │ ◄───────────────────────────────────────── │                      │
    │  GET …/master.m3u8   (no token, no cookie) │                      │
    │ ─────────────────────────────────────────► │  403 Forbidden       │
    │ ◄──────────── no media ─────────────────── │  (never touches R2)   │
```

## Prerequisites

- `uv sync` in `griddy-archive-manager` (Django + packaging deps).
- `ffmpeg`/`ffprobe` on `PATH` (the packager shells out to them).
- `cd video-worker && npm install` (Worker + hls.js + Playwright).
- `npx playwright install chromium firefox` (one-time browser download).
- `video-worker/.dev.vars` with `PLAYBACK_TOKEN_SECRET="dev-secret"` (already
  present; it must equal Django's `PLAYBACK_TOKEN_SECRET` so signatures agree).

No Cloudflare account, R2 bucket, or `wrangler login` is required — everything
runs against Miniflare's on-disk R2 under `video-worker/.wrangler/state`.

## Step 1 — package a real game into the local R2 store

```bash
cd griddy-archive-manager
PLAYBACK_TOKEN_SECRET=dev-secret uv run manage.py poc_load_game \
  "/mnt/g/NFL (1920)/NFL Condensed Games (1920)/Season 2025/NFL Condensed Game - s2025e005 - 2025_Wk01_MIA_at_IND.mp4" \
  --game-id 2025001 \
  --wrangler-cwd video-worker \
  --measurements-out docs/video-poc/measurements.json \
  --mint-token
```

`poc_load_game` probes the source, remuxes it to CMAF/HLS (a lossless
`-c copy` — the catalog is ~99% H.264/AAC), and loads the objects into the local
R2 bucket under `games/2025001/` (the prefix the playback URL resolves). It
writes `docs/video-poc/measurements.json` and, with `--mint-token`, prints a
ready-to-paste signed playback URL.

Measured on this run (see `measurements.json`):

| Metric | Value |
| --- | --- |
| Source | MIA @ IND, 2025 Wk1 condensed, 1.25 GB |
| Packaged size | 1.25 GB (**0.9996× source** — lossless remux) |
| Segments | 324 × ~6 s (+ `init.mp4` + `master.m3u8`) |
| Duration | 32.3 min |
| Transcoded | no (stream copy) |

## Step 2 — run the Worker

```bash
cd video-worker
npm run dev        # wrangler dev on http://localhost:8787, BUCKET -> local R2
```

## Step 3 — manual playback in a real browser

```bash
# In a second terminal — serves the hls.js player on an allowlisted origin.
cd video-worker
npm run poc:player   # http://localhost:5173
```

Open the signed URL `poc_load_game --mint-token` printed, and paste it into the
player as the `src` query param:

```
http://localhost:5173/?src=<URL-encoded master.m3u8?t=token>
```

Click **Play** (forward playback) and **Seek +60s** (scrubbing). The status pane
shows `MANIFEST_PARSED`, each `FRAG_LOADED`, and the current time.

### Three-browser matrix

| Browser | Engine | How | Automated? |
| --- | --- | --- | --- |
| Chrome / Edge | Chromium | hls.js (MSE) | ✅ Playwright |
| Firefox | Gecko | hls.js (MSE) | ✅ Playwright |
| Safari | WebKit | **native HLS** (`<video src>`) — the player auto-falls back when `Hls.isSupported()` is false | ⚠️ manual, macOS only |

**Safari is manual.** WebKit on Linux (the Playwright `webkit` build) does not
reliably decode the catalog's H.264/AAC in MSE, and real Safari only runs on
macOS. To verify Safari: on a Mac, run Steps 1–3 against the same local Worker
(or a tunnel to it) and confirm the game plays, seeks, and that a tokenless URL
shows no media. The player already serves Safari via native HLS, so no code
changes are needed — only a human with a Mac.

## Step 4 — automated playback (Chromium + Firefox)

```bash
cd video-worker
npm run test:e2e     # playwright test
```

Playwright boots both servers (`wrangler dev` + the player static server) and,
in **Chromium and Firefox**, asserts the full chain against the packaged game:

- the token-bearing manifest loads and hls.js parses it;
- segments stream through the gate (the session cookie rides them);
- `play()` advances `currentTime` (real forward playback / decode);
- **seek** fires fresh segment fetches and lands near the target;
- an unauthorized manifest, a tampered token, a bare segment, and a
  wrong-game token each return **403 with no media**, and the player surfaces
  the 403 as a fatal load error.

The suite mints its token with the same secret + claims as
`gam.playback.tokens`, so the Worker accepts it exactly as a Django-minted one.

## Step 5 — auth-gating spot check (optional, by hand)

```bash
# Authorized (prints 200 and a Set-Cookie header):
curl -i "http://localhost:8787/games/2025001/master.m3u8?t=<token>" | head -n 20
# Unauthorized (403, body is just "Forbidden"):
curl -i "http://localhost:8787/games/2025001/master.m3u8"
```

> curl will not re-send a `Secure` cookie over `http://localhost`; to exercise
> the cookie path by hand, copy the `Set-Cookie` value and pass it explicitly
> with `-H "Cookie: griddy_video_session=<value>"`.

## Step 6 — cost model

```bash
cd griddy-archive-manager
uv run python scripts/video_cost_model.py \
  --measurements docs/video-poc/measurements.json -o docs/video-poc/cost-model.md
```

This projects the local measurement across the full catalog against published
Cloudflare R2 + Workers pricing. Result: **~$54/mo at pilot volume rising to
~$78/mo at 100k streams/mo** — firmly the ~$10s/mo class ADR-0008 assumed, not
~$1000s/mo. Storage dominates and is fixed; reads/Workers stay small because R2
egress is free. See [`cost-model.md`](./cost-model.md) for the full table.

## What this PoC does **not** do

- No real R2/Workers are provisioned (local-first by design — TGF-340 promotes
  to real Cloudflare, configuration-only).
- Player UI is a throwaway hls.js harness; the production player is vidstack
  (TGF-335).
- Token minting in the automated suite is local; the production path is the
  Django playback API (TGF-360) behind Clerk auth.
