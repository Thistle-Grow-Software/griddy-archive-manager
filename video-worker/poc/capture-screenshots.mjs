// Capture PoC player screenshots for the PR / runbook (ADR-0008, TGF-363).
//
// Drives the same player.html the Playwright suite does, but headed-quality
// screenshots into docs/screenshots/video-poc-playback/. Assumes the two PoC
// servers are already up (wrangler dev :8787 + poc/serve.mjs :5173); start them
// with `npm run dev` and `npm run poc:player`, or let this script's sibling
// npm script bring them up. Mints its own HS256 token with the shared dev secret
// (self-contained — mirrors gam.playback.tokens claims).

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const WORKER = "http://localhost:8787";
const PLAYER = "http://localhost:5173";
const GAME_ID = "2025001";
const SECRET = "dev-secret";

const here = dirname(fileURLToPath(import.meta.url));
const outDir = join(here, "..", "..", "docs", "screenshots", "video-poc-playback");

function b64url(bytes) {
	return Buffer.from(bytes)
		.toString("base64")
		.replace(/\+/g, "-")
		.replace(/\//g, "_")
		.replace(/=+$/, "");
}

async function mintToken() {
	const now = Math.floor(Date.now() / 1000);
	const header = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
	const payload = b64url(
		JSON.stringify({
			sub: "poc-user",
			gid: GAME_ID,
			iat: now,
			exp: now + 600,
			iss: "griddy-api",
			aud: "griddy-video-worker",
		}),
	);
	const data = `${header}.${payload}`;
	const key = await crypto.subtle.importKey(
		"raw",
		new TextEncoder().encode(SECRET),
		{ name: "HMAC", hash: "SHA-256" },
		false,
		["sign"],
	);
	const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(data));
	return `${data}.${b64url(new Uint8Array(sig))}`;
}

const playerUrl = (src) => `${PLAYER}/?src=${encodeURIComponent(src)}`;

async function main() {
	await mkdir(outDir, { recursive: true });
	const browser = await chromium.launch();
	const page = await browser.newPage({ viewport: { width: 1100, height: 760 } });

	// 1) Authorized playback.
	const token = await mintToken();
	const manifest = `${WORKER}/games/${GAME_ID}/master.m3u8?t=${token}`;
	await page.goto(playerUrl(manifest));
	await page.waitForFunction(() => window.__poc?.fragsLoaded > 0, null, { timeout: 30000 });
	await page.getByTestId("play").click();
	await page.waitForFunction(() => window.__poc?.currentTime > 2, null, { timeout: 30000 });
	await page.screenshot({ path: join(outDir, "01-authorized-playback.png") });
	console.log("wrote 01-authorized-playback.png");

	// 2) After a seek.
	await page.getByTestId("seek").click();
	await page.waitForFunction(() => window.__poc?.seeked === true, null, { timeout: 30000 });
	await page.waitForTimeout(800);
	await page.screenshot({ path: join(outDir, "02-after-seek.png") });
	console.log("wrote 02-after-seek.png");

	// 3) Unauthorized -> 403 surfaced in the player. Clear the session cookie the
	//    authorized run set, otherwise the cookie would re-authorize this request.
	await page.context().clearCookies();
	await page.goto(playerUrl(`${WORKER}/games/${GAME_ID}/master.m3u8`));
	await page.waitForFunction(() => window.__poc?.errorStatus === 403, null, { timeout: 20000 });
	await page.waitForTimeout(300);
	await page.screenshot({ path: join(outDir, "03-unauthorized-403.png") });
	console.log("wrote 03-unauthorized-403.png");

	await browser.close();
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
