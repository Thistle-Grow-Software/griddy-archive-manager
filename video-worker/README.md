# griddy-video-worker

Cloudflare Worker that fronts the R2 video bucket and gates every HLS request
(ADR-0008, TGF-361). It is the access-control enforcement point for v1 game-film
delivery: the playback API mints a short-lived token, this Worker validates it,
exchanges it for a signed session cookie, and streams objects from its R2
binding — with Range support for scrubbing and CORS for the portal origin.

This is a standalone Node/TypeScript subproject of `griddy-archive-manager`; it
has its own `package.json` and is not part of the Django app's `uv` environment.

## How the gate works

1. The portal calls Django's `GET /api/games/{id}/playback` with its Clerk JWT.
   Django checks entitlement and returns
   `{type, url, expires_at}` where `url` is
   `{VIDEO_ORIGIN_URL}/games/{id}/master.m3u8?t=<token>`.
2. The player loads that manifest. The Worker verifies the HS256 `t` token
   (issuer `griddy-api`, audience `griddy-video-worker`), and on success sets a
   signed `griddy_video_session` cookie scoped to `Path=/games/{id}/`, then
   streams the manifest from R2.
3. The player requests segments (relative URLs under that path). They carry the
   cookie (no token); the Worker verifies it and streams each object, honoring
   `Range` with `206 Partial Content`.

Any request whose token **and** cookie are missing, expired, invalid, or scoped
to a different game gets `403 Forbidden` and no media.

The session cookie's TTL is **6 hours** (`SESSION_COOKIE_TTL_SECONDS`),
comfortably longer than a full game, so playback never hits a mid-stream 403 and
no refresh round-trip is needed.

## Token/secret contract

`PLAYBACK_TOKEN_SECRET` here **must** equal Django's `PLAYBACK_TOKEN_SECRET`
(`gam/settings.py`, `gam.playback.tokens`). Both sides use HS256. Rotating the
secret invalidates outstanding playback URLs on both sides at once.

## Local development (cost-free PoC)

```bash
npm install
cp .dev.vars.example .dev.vars      # set PLAYBACK_TOKEN_SECRET to match Django
npm run dev                          # wrangler dev on http://localhost:8787
```

`wrangler dev` binds `BUCKET` to Miniflare's local R2 simulation under
`.wrangler/state`. Load packaged HLS into that same store from the Django side:

```bash
# from griddy-archive-manager/
uv run manage.py package_hls "/path/to/a/game/root" --limit-per-league 1 \
    --local --bucket griddy-video --wrangler-cwd video-worker
```

(`--wrangler-cwd video-worker` runs `wrangler` from this project so its config
and `.wrangler/state` line up with `wrangler dev`.)

## Tests

```bash
npm test
```

Tests run inside `workerd` via `@cloudflare/vitest-pool-workers`, against the
real Worker with `BUCKET` bound to an isolated local R2. They cover the token →
cookie exchange, segment streaming, 403 gating (missing/expired/invalid/wrong-
game credentials), Range/206 with `Content-Range`, HEAD, and the credentialed
CORS contract.

## Promotion to production (configuration only)

The Worker code is identical in local and production. To deploy to real R2 on a
custom video origin (deferred beyond the PoC, gated on TGF-340):

1. Create the remote bucket; the `bucket_name` in `wrangler.jsonc` already
   points at `griddy-video`.
2. `wrangler secret put PLAYBACK_TOKEN_SECRET` (same value as Django).
3. Add the `routes`/custom domain (`video.dev.griddy.football`) and set
   `ALLOWED_ORIGINS` to the deployed portal origin.
4. `npm run deploy`.

No source changes are required for any of the above.
