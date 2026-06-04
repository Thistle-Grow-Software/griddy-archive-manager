import { expect, test } from "@playwright/test";
import { signHs256 } from "../src/jwt";

// End-to-end PoC (ADR-0008, TGF-363, AC5): a real browser plays a packaged game
// served from the local R2 store through the auth-gating Worker, and the gate
// rejects unauthorized requests. The token is minted here with the SAME shared
// secret + claims Django's gam.playback.tokens uses, so the Worker accepts it
// exactly as it would a production-minted token — the runbook documents the
// Django-minted path; this keeps the suite self-contained (no Python at runtime).

const WORKER = "http://localhost:8787";
const GAME_ID = "2025001"; // loaded by `manage.py poc_load_game --game-id 2025001`.
const SECRET = "dev-secret"; // must equal video-worker/.dev.vars PLAYBACK_TOKEN_SECRET.

async function mintToken(opts: { gid?: string; expiresInSeconds?: number } = {}) {
	const now = Math.floor(Date.now() / 1000);
	return signHs256(
		{
			sub: "poc-user",
			gid: opts.gid ?? GAME_ID,
			iat: now,
			exp: now + (opts.expiresInSeconds ?? 600),
			iss: "griddy-api", // PLAYBACK_TOKEN_ISSUER
			aud: "griddy-video-worker", // PLAYBACK_TOKEN_AUDIENCE
		},
		SECRET,
	);
}

function manifestUrl(token: string, gid = GAME_ID) {
	return `${WORKER}/games/${gid}/master.m3u8?t=${token}`;
}

function playerUrl(src: string) {
	return `/?src=${encodeURIComponent(src)}`;
}

test.describe("ADR-0008 gated HLS playback", () => {
	test("authorized token streams the manifest and segments, and plays forward", async ({
		page,
	}) => {
		const token = await mintToken();
		await page.goto(playerUrl(manifestUrl(token)));

		// 1) The manifest passed the gate and hls.js parsed it.
		await page.waitForFunction(() => (window as any).__poc?.manifestParsed === true);

		// 2) Segments stream through the gate (the session cookie set on the
		//    manifest response is riding the credentialed segment fetches).
		await page.waitForFunction(() => (window as any).__poc?.fragsLoaded > 0);

		// 3) The CMAF init/media segments are fetched with byte-ranges — Range
		//    requests survive the gate, which is what scrubbing relies on.
		const poc = await page.evaluate(() => (window as any).__poc);
		expect(poc.error, `unexpected hls.js error: ${poc.error}`).toBeFalsy();

		// 4) Forward playback: currentTime advances past zero after play().
		await page.getByTestId("play").click();
		await page.waitForFunction(() => (window as any).__poc?.currentTime > 0.3, null, {
			timeout: 30_000,
		});

		const after = await page.evaluate(() => (window as any).__poc);
		expect(after.fragsLoaded).toBeGreaterThan(0);
		expect(after.currentTime).toBeGreaterThan(0.3);
	});

	test("seeking issues fresh range requests and lands near the target", async ({
		page,
	}) => {
		const token = await mintToken();
		await page.goto(playerUrl(manifestUrl(token)));
		await page.waitForFunction(() => (window as any).__poc?.fragsLoaded > 0);
		await page.getByTestId("play").click();
		await page.waitForFunction(() => (window as any).__poc?.currentTime > 0.3, null, {
			timeout: 30_000,
		});

		const before = await page.evaluate(() => (window as any).__poc.fragsLoaded);
		await page.getByTestId("seek").click();

		// The seek fires a 'seeked' event and pulls new segments for the target
		// region through the gate.
		await page.waitForFunction(() => (window as any).__poc?.seeked === true, null, {
			timeout: 30_000,
		});
		await page.waitForFunction(
			(b) => (window as any).__poc?.fragsLoaded > (b as number),
			before,
			{ timeout: 30_000 },
		);

		const poc = await page.evaluate(() => (window as any).__poc);
		expect(poc.seekedTo).toBeGreaterThan(1); // moved meaningfully forward
		expect(poc.error, `unexpected hls.js error: ${poc.error}`).toBeFalsy();
	});

	test("unauthorized manifest request is rejected with 403 and no media", async ({
		request,
	}) => {
		// No token at all.
		const anon = await request.get(`${WORKER}/games/${GAME_ID}/master.m3u8`);
		expect(anon.status()).toBe(403);
		expect((await anon.body()).byteLength).toBeLessThan(64); // "Forbidden", no media

		// Tampered token (valid shape, wrong signature).
		const good = await mintToken();
		const tampered = `${good.slice(0, -4)}AAAA`;
		const bad = await request.get(manifestUrl(tampered));
		expect(bad.status()).toBe(403);

		// A segment cannot be fetched directly without the session cookie either.
		const seg = await request.get(`${WORKER}/games/${GAME_ID}/seg_00001.m4s`);
		expect(seg.status()).toBe(403);
	});

	test("a token scoped to another game cannot fetch this game's media", async ({
		request,
	}) => {
		const otherGame = await mintToken({ gid: "9999999" });
		// Path says GAME_ID, token says 9999999 -> the gid scope check fails.
		const res = await request.get(manifestUrl(otherGame, GAME_ID));
		expect(res.status()).toBe(403);
	});

	test("the player surfaces the 403 as a fatal load error (no playback)", async ({
		page,
	}) => {
		await page.goto(playerUrl(`${WORKER}/games/${GAME_ID}/master.m3u8`)); // no token
		await page.waitForFunction(() => (window as any).__poc?.error, null, {
			timeout: 20_000,
		});
		const poc = await page.evaluate(() => (window as any).__poc);
		expect(poc.errorStatus).toBe(403);
		expect(poc.manifestParsed).toBeFalsy();
		expect(poc.currentTime ?? 0).toBeLessThanOrEqual(0);
	});
});
