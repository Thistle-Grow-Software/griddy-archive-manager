import { env, SELF } from "cloudflare:test";
import { beforeAll, describe, expect, it } from "vitest";
import { signHs256 } from "../src/jwt";

// Matches the test-only secret injected in vitest.config.ts. In production this
// equals Django's PLAYBACK_TOKEN_SECRET; the suite mints tokens/cookies with it
// exactly as the playback API and this Worker would.
const SECRET = "test-secret-do-not-use-in-prod";
const ORIGIN = "http://localhost:5173";
const GAME_ID = "5";
const MANIFEST_KEY = `games/${GAME_ID}/master.m3u8`;
const SEGMENT_KEY = `games/${GAME_ID}/seg0.m4s`;
const MANIFEST_BODY = "#EXTM3U\n#EXT-X-VERSION:7\nseg0.m4s\n";
const SEGMENT_BYTES = new Uint8Array(1000).map((_, i) => i % 256);

function nowSeconds(): number {
	return Math.floor(Date.now() / 1000);
}

/** Mint a playback token like the Django API would (issuer/audience match). */
function mintToken(overrides: Record<string, unknown> = {}, secret = SECRET): Promise<string> {
	return signHs256(
		{
			sub: "user_abc",
			gid: GAME_ID,
			iat: nowSeconds(),
			exp: nowSeconds() + 900,
			iss: "griddy-api",
			aud: "griddy-video-worker",
			...overrides,
		},
		secret,
	);
}

/** Mint a session cookie value like the Worker would after a token exchange. */
function mintCookie(overrides: Record<string, unknown> = {}): Promise<string> {
	return signHs256(
		{
			sub: "user_abc",
			gid: GAME_ID,
			iat: nowSeconds(),
			exp: nowSeconds() + 21600,
			iss: "griddy-video-worker",
			aud: "griddy-video-session",
			...overrides,
		},
		SECRET,
	);
}

function url(path: string): string {
	return `http://localhost:8787${path}`;
}

/** Extract a cookie value from a Set-Cookie header line. */
function cookieValue(setCookie: string): string {
	return setCookie.split(";")[0].split("=").slice(1).join("=");
}

beforeAll(async () => {
	await env.BUCKET.put(MANIFEST_KEY, MANIFEST_BODY, {
		httpMetadata: { contentType: "application/vnd.apple.mpegurl" },
	});
	await env.BUCKET.put(SEGMENT_KEY, SEGMENT_BYTES, {
		httpMetadata: { contentType: "video/iso.segment" },
	});
});

describe("manifest request with a valid token", () => {
	it("returns the manifest with 200 and sets a signed session cookie", async () => {
		const token = await mintToken();
		const res = await SELF.fetch(url(`/${MANIFEST_KEY}?t=${token}`), {
			headers: { Origin: ORIGIN },
		});

		expect(res.status).toBe(200);
		expect(await res.text()).toBe(MANIFEST_BODY);
		expect(res.headers.get("Content-Type")).toBe("application/vnd.apple.mpegurl");

		const setCookie = res.headers.get("Set-Cookie") ?? "";
		expect(setCookie).toContain("griddy_video_session=");
		expect(setCookie).toContain("SameSite=None");
		expect(setCookie).toContain("Secure");
		expect(setCookie).toContain("HttpOnly");
		expect(setCookie).toContain(`Path=/games/${GAME_ID}/`);
	});
});

describe("segment request", () => {
	it("streams the object with 200 when a valid cookie is present", async () => {
		const cookie = await mintCookie();
		const res = await SELF.fetch(url(`/${SEGMENT_KEY}`), {
			headers: { Origin: ORIGIN, Cookie: `griddy_video_session=${cookie}` },
		});

		expect(res.status).toBe(200);
		expect(res.headers.get("Accept-Ranges")).toBe("bytes");
		expect(res.headers.get("Content-Length")).toBe("1000");
		const body = new Uint8Array(await res.arrayBuffer());
		expect(body.length).toBe(1000);
		expect(Array.from(body.slice(0, 4))).toEqual([0, 1, 2, 3]);
	});

	it("works end to end: cookie from the manifest exchange authorizes the segment", async () => {
		const token = await mintToken();
		const manifestRes = await SELF.fetch(url(`/${MANIFEST_KEY}?t=${token}`), {
			headers: { Origin: ORIGIN },
		});
		const setCookie = manifestRes.headers.get("Set-Cookie") ?? "";
		await manifestRes.text(); // drain the R2-backed body so isolated storage can unwind
		const cookie = cookieValue(setCookie);

		const segRes = await SELF.fetch(url(`/${SEGMENT_KEY}`), {
			headers: { Origin: ORIGIN, Cookie: `griddy_video_session=${cookie}` },
		});
		expect(segRes.status).toBe(200);
		await segRes.arrayBuffer();
	});
});

describe("unauthorized requests get a clean 403 and no media", () => {
	it("403s a manifest with no token or cookie", async () => {
		const res = await SELF.fetch(url(`/${MANIFEST_KEY}`), { headers: { Origin: ORIGIN } });
		expect(res.status).toBe(403);
		expect(await res.text()).not.toContain("#EXTM3U");
	});

	it("403s a segment with no cookie", async () => {
		const res = await SELF.fetch(url(`/${SEGMENT_KEY}`), { headers: { Origin: ORIGIN } });
		expect(res.status).toBe(403);
		expect((await res.arrayBuffer()).byteLength).toBeLessThan(SEGMENT_BYTES.length);
	});

	it("403s an expired token", async () => {
		const token = await mintToken({ exp: nowSeconds() - 60 });
		const res = await SELF.fetch(url(`/${MANIFEST_KEY}?t=${token}`), {
			headers: { Origin: ORIGIN },
		});
		expect(res.status).toBe(403);
	});

	it("403s a token signed with the wrong secret", async () => {
		const token = await mintToken({}, "the-wrong-secret");
		const res = await SELF.fetch(url(`/${MANIFEST_KEY}?t=${token}`), {
			headers: { Origin: ORIGIN },
		});
		expect(res.status).toBe(403);
	});

	it("403s an expired cookie", async () => {
		const cookie = await mintCookie({ exp: nowSeconds() - 60 });
		const res = await SELF.fetch(url(`/${SEGMENT_KEY}`), {
			headers: { Origin: ORIGIN, Cookie: `griddy_video_session=${cookie}` },
		});
		expect(res.status).toBe(403);
	});

	it("403s a token scoped to a different game", async () => {
		const token = await mintToken({ gid: "999" });
		const res = await SELF.fetch(url(`/${MANIFEST_KEY}?t=${token}`), {
			headers: { Origin: ORIGIN },
		});
		expect(res.status).toBe(403);
	});
});

describe("Range requests", () => {
	it("returns 206 with a correct Content-Range for a bounded range", async () => {
		const cookie = await mintCookie();
		const res = await SELF.fetch(url(`/${SEGMENT_KEY}`), {
			headers: { Origin: ORIGIN, Cookie: `griddy_video_session=${cookie}`, Range: "bytes=0-99" },
		});
		expect(res.status).toBe(206);
		expect(res.headers.get("Content-Range")).toBe("bytes 0-99/1000");
		expect(res.headers.get("Content-Length")).toBe("100");
		const body = new Uint8Array(await res.arrayBuffer());
		expect(body.length).toBe(100);
		expect(Array.from(body.slice(0, 3))).toEqual([0, 1, 2]);
	});

	it("handles a mid-object range", async () => {
		const cookie = await mintCookie();
		const res = await SELF.fetch(url(`/${SEGMENT_KEY}`), {
			headers: {
				Origin: ORIGIN,
				Cookie: `griddy_video_session=${cookie}`,
				Range: "bytes=500-599",
			},
		});
		expect(res.status).toBe(206);
		expect(res.headers.get("Content-Range")).toBe("bytes 500-599/1000");
		expect(res.headers.get("Content-Length")).toBe("100");
		await res.arrayBuffer();
	});

	it("handles a suffix range", async () => {
		const cookie = await mintCookie();
		const res = await SELF.fetch(url(`/${SEGMENT_KEY}`), {
			headers: { Origin: ORIGIN, Cookie: `griddy_video_session=${cookie}`, Range: "bytes=-50" },
		});
		expect(res.status).toBe(206);
		expect(res.headers.get("Content-Range")).toBe("bytes 950-999/1000");
		expect(res.headers.get("Content-Length")).toBe("50");
		await res.arrayBuffer();
	});
});

describe("HEAD requests", () => {
	it("returns headers without a body", async () => {
		const cookie = await mintCookie();
		const res = await SELF.fetch(url(`/${SEGMENT_KEY}`), {
			method: "HEAD",
			headers: { Origin: ORIGIN, Cookie: `griddy_video_session=${cookie}` },
		});
		expect(res.status).toBe(200);
		expect(res.headers.get("Content-Length")).toBe("1000");
		expect(res.headers.get("Accept-Ranges")).toBe("bytes");
		expect((await res.arrayBuffer()).byteLength).toBe(0);
	});
});

describe("CORS", () => {
	it("answers preflight with credentialed, non-wildcard headers", async () => {
		const res = await SELF.fetch(url(`/${SEGMENT_KEY}`), {
			method: "OPTIONS",
			headers: {
				Origin: ORIGIN,
				"Access-Control-Request-Method": "GET",
				"Access-Control-Request-Headers": "range",
			},
		});
		expect(res.status).toBe(204);
		expect(res.headers.get("Access-Control-Allow-Origin")).toBe(ORIGIN);
		expect(res.headers.get("Access-Control-Allow-Credentials")).toBe("true");
		expect(res.headers.get("Access-Control-Allow-Methods")).toContain("GET");
		expect(res.headers.get("Access-Control-Allow-Methods")).toContain("HEAD");
		expect(res.headers.get("Access-Control-Allow-Headers")?.toLowerCase()).toContain("range");
	});

	it("exposes the headers HLS scrubbing needs and never emits a wildcard", async () => {
		const cookie = await mintCookie();
		const res = await SELF.fetch(url(`/${SEGMENT_KEY}`), {
			headers: { Origin: ORIGIN, Cookie: `griddy_video_session=${cookie}` },
		});
		const acao = res.headers.get("Access-Control-Allow-Origin");
		expect(acao).toBe(ORIGIN);
		expect(acao).not.toBe("*");
		const expose = res.headers.get("Access-Control-Expose-Headers") ?? "";
		for (const header of ["Content-Length", "Content-Range", "Accept-Ranges", "ETag"]) {
			expect(expose).toContain(header);
		}
		await res.arrayBuffer();
	});

	it("does not echo an origin that is not on the allowlist", async () => {
		const token = await mintToken();
		const res = await SELF.fetch(url(`/${MANIFEST_KEY}?t=${token}`), {
			headers: { Origin: "https://evil.example.com" },
		});
		expect(res.headers.get("Access-Control-Allow-Origin")).toBeNull();
		await res.text();
	});
});
