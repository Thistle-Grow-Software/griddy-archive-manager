"""Short-lived playback tokens for the v1 HLS delivery path (TGF-360, ADR-0008).

The API mints these tokens; the Cloudflare Worker (TGF-361 / TGF-363) verifies
them. Both ends import :mod:`gam.playback.tokens` so the signing contract has
exactly one definition.
"""
