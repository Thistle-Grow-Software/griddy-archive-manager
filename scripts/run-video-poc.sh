#!/usr/bin/env bash
#
# run-video-poc.sh — bring up the TGF-363 video PoC and print a ready-to-open URL.
#
# Starts (or reuses) the two local servers — the Worker on :8787 (wrangler dev,
# bound to the local Miniflare R2) and the hls.js player on :5173 — mints a fresh
# ADR-0008 playback token via Django, and prints the player URL to open in a
# browser. The game is packaged into local R2 on first run; later runs just mint
# a new token (tokens are short-lived, packaging is not).
#
# Usage:
#   scripts/run-video-poc.sh
#
# Environment overrides:
#   POC_SOURCE          Source video to package if the game isn't loaded yet.
#   POC_GAME_ID         Game id (default 2025001).
#   POC_FORCE_PACKAGE=1 Re-package even if the game is already in local R2.
set -euo pipefail

# --- Resolve paths -----------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKER_DIR="$GAM_DIR/video-worker"

# --- Config ------------------------------------------------------------------
GAME_ID="${POC_GAME_ID:-2025001}"
SECRET="${PLAYBACK_TOKEN_SECRET:-dev-secret}"
WORKER_PORT=8787
PLAYER_PORT=5173
DEFAULT_SOURCE="/mnt/g/NFL (1920)/NFL Condensed Games (1920)/Season 2025/NFL Condensed Game - s2025e005 - 2025_Wk01_MIA_at_IND.mp4"
SOURCE="${POC_SOURCE:-$DEFAULT_SOURCE}"
WRANGLER_LOG="/tmp/poc-wrangler.log"
PLAYER_LOG="/tmp/poc-player.log"

STARTED_PIDS=()

STARTED_WORKER=false
STARTED_PLAYER=false

cleanup() {
	if [ "${#STARTED_PIDS[@]}" -gt 0 ]; then
		echo ""
		echo "Stopping servers this script started…"
		for pid in "${STARTED_PIDS[@]}"; do
			kill "$pid" 2>/dev/null || true
		done
		# wrangler dev spawns a detached workerd grandchild the parent PID misses.
		[ "$STARTED_WORKER" = true ] && pkill -f "wrangler dev --port $WORKER_PORT" 2>/dev/null || true
		[ "$STARTED_PLAYER" = true ] && pkill -f "poc/serve.mjs" 2>/dev/null || true
	fi
}
trap cleanup EXIT INT TERM

http_code() {
	local code
	code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$1" 2>/dev/null)" || true
	echo "${code:-000}"
}
worker_up() { [ "$(http_code "http://localhost:$WORKER_PORT/")" != "000" ]; }
player_up() { [ "$(http_code "http://localhost:$PLAYER_PORT/player.html")" = "200" ]; }

wait_until() { # <fn> <label> <timeout-seconds>
	local fn="$1" label="$2" timeout="$3" waited=0
	while ! "$fn"; do
		sleep 0.5
		waited=$((waited + 1))
		if [ "$waited" -gt $((timeout * 2)) ]; then
			echo "ERROR: $label did not come up within ${timeout}s." >&2
			exit 1
		fi
	done
}

# --- 1. Worker (wrangler dev) ------------------------------------------------
if worker_up; then
	echo "✓ Worker already running on :$WORKER_PORT (reusing)."
else
	echo "→ Starting Worker (wrangler dev) on :$WORKER_PORT…"
	(cd "$WORKER_DIR" && exec npx wrangler dev --port "$WORKER_PORT") \
		>"$WRANGLER_LOG" 2>&1 &
	STARTED_PIDS+=("$!")
	STARTED_WORKER=true
	wait_until worker_up "Worker" 120
	echo "✓ Worker ready (logs: $WRANGLER_LOG)."
fi

# --- 2. Player static server -------------------------------------------------
if player_up; then
	echo "✓ Player server already running on :$PLAYER_PORT (reusing)."
else
	echo "→ Starting player server on :$PLAYER_PORT…"
	(cd "$WORKER_DIR" && exec node poc/serve.mjs) >"$PLAYER_LOG" 2>&1 &
	STARTED_PIDS+=("$!")
	STARTED_PLAYER=true
	wait_until player_up "Player server" 30
	echo "✓ Player server ready (logs: $PLAYER_LOG)."
fi

# --- 3. Mint a token (packaging only if the game isn't loaded yet) ------------
mint_url() { # prints the signed manifest URL
	(cd "$GAM_DIR" && PLAYBACK_TOKEN_SECRET="$SECRET" \
		uv run manage.py poc_load_game --game-id "$GAME_ID" \
		--wrangler-cwd video-worker --skip-package 2>/dev/null) |
		grep -Eo "http://localhost:$WORKER_PORT/games/[^ ]*master\.m3u8\?t=[A-Za-z0-9._-]+" |
		head -n1
}

package_game() {
	if [ ! -f "$SOURCE" ]; then
		echo "ERROR: game not in local R2 and source file not found:" >&2
		echo "  $SOURCE" >&2
		echo "Set POC_SOURCE=/path/to/a/2016+/game.mp4 and re-run." >&2
		exit 1
	fi
	echo "→ Packaging '$(basename "$SOURCE")' into local R2 (one-time)…"
	(cd "$GAM_DIR" && PLAYBACK_TOKEN_SECRET="$SECRET" \
		uv run manage.py poc_load_game "$SOURCE" --game-id "$GAME_ID" \
		--wrangler-cwd video-worker)
}

echo "→ Minting playback token for game $GAME_ID…"
MANIFEST_URL="$(mint_url)"
if [ -z "$MANIFEST_URL" ]; then
	echo "ERROR: failed to mint a playback token (is VIDEO_ORIGIN_URL set to :$WORKER_PORT?)." >&2
	exit 1
fi

probe="$(http_code "$MANIFEST_URL")"
if [ "${POC_FORCE_PACKAGE:-0}" = "1" ] || [ "$probe" = "404" ]; then
	package_game
	MANIFEST_URL="$(mint_url)" # fresh token after load
elif [ "$probe" != "200" ]; then
	echo "WARNING: manifest probe returned HTTP $probe (expected 200)." >&2
fi

# --- 4. Build and print the player URL ---------------------------------------
encode() { uv run --project "$GAM_DIR" python -c \
	'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }
PLAYER_URL="http://localhost:$PLAYER_PORT/?src=$(encode "$MANIFEST_URL")"

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "  Open this URL in Chrome or Firefox (token valid ~15 min):"
echo ""
echo "  $PLAYER_URL"
echo ""
echo "  Then click Play, and Seek +60s. For the 403 path, open the player with"
echo "  a tokenless src: http://localhost:$PLAYER_PORT/?src=http://localhost:$WORKER_PORT/games/$GAME_ID/master.m3u8"
echo "════════════════════════════════════════════════════════════════════════"

# --- 5. Keep alive if we started the servers ---------------------------------
if [ "${#STARTED_PIDS[@]}" -gt 0 ]; then
	echo ""
	echo "Servers running in this terminal. Press Ctrl-C to stop them."
	wait
else
	echo ""
	echo "(Reused already-running servers; leaving them up. Re-run for a fresh token.)"
fi
