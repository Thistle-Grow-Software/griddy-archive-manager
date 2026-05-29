// Video gateway Worker (ADR-0008, TGF-361).
//
// Fronts an R2 bucket of packaged HLS and authorizes every request before
// streaming an object:
//
//   1. The portal calls Django's playback API, which mints a short-lived,
//      game-scoped HS256 token and returns a URL of the form
//      `{origin}/games/{id}/master.m3u8?t=<token>` (gam.playback.tokens).
//   2. The player loads that manifest. This Worker validates the token and, on
//      success, sets a longer-lived signed session cookie scoped to the game's
//      path, then streams the manifest from R2.
//   3. The player then requests segments (relative URLs under the same path).
//      Those carry the cookie (no token), which the Worker validates before
//      streaming each object — with Range support for HLS scrubbing.
//
// Any request without a valid token or cookie gets a 403 and no media. The
// Worker is environment-agnostic: only the R2 binding target and the (secret)
// signing key change between local Miniflare and production R2.

import { corsHeaders, preflightResponse, resolveAllowedOrigin } from "./cors";
import { signHs256, verifyHs256 } from "./jwt";

export interface Env {
	BUCKET: R2Bucket;
	/** Shared HMAC secret; MUST equal Django's PLAYBACK_TOKEN_SECRET. */
	PLAYBACK_TOKEN_SECRET: string;
	ALLOWED_ORIGINS: string;
	PLAYBACK_TOKEN_ISSUER: string;
	PLAYBACK_TOKEN_AUDIENCE: string;
	SESSION_COOKIE_NAME: string;
	SESSION_COOKIE_ISSUER: string;
	SESSION_COOKIE_AUDIENCE: string;
	SESSION_COOKIE_TTL_SECONDS: string;
}

interface AuthResult {
	ok: boolean;
	/** True when authorized via a fresh token, so the response should set a cookie. */
	setCookie?: boolean;
	gid?: string;
	sub?: string;
}

const DEFAULT_COOKIE_TTL_SECONDS = 21600; // 6h fallback if the var is unset/invalid.

function nowSeconds(): number {
	return Math.floor(Date.now() / 1000);
}

/** Pull the game id out of a `/games/{id}/...` path, if it follows that shape. */
function gameIdFromPath(pathname: string): string | null {
	const match = /^\/games\/([^/]+)\//.exec(pathname);
	return match ? match[1] : null;
}

function readCookie(cookieHeader: string | null, name: string): string | null {
	if (!cookieHeader) {
		return null;
	}
	for (const part of cookieHeader.split(";")) {
		const eq = part.indexOf("=");
		if (eq === -1) {
			continue;
		}
		if (part.slice(0, eq).trim() === name) {
			return part.slice(eq + 1).trim();
		}
	}
	return null;
}

/**
 * Authorize a request via either the playback token (`?t=`) or the session
 * cookie. When a `/games/{id}/` path is present, the credential's `gid` claim
 * must match it, so a token minted for one game cannot fetch another's media.
 */
async function authorize(request: Request, url: URL, env: Env): Promise<AuthResult> {
	const pathGid = gameIdFromPath(url.pathname);
	const scopedTo = (claimGid: unknown): boolean =>
		pathGid === null || String(claimGid) === pathGid;

	const token = url.searchParams.get("t");
	if (token) {
		const result = await verifyHs256(token, env.PLAYBACK_TOKEN_SECRET, {
			issuer: env.PLAYBACK_TOKEN_ISSUER,
			audience: env.PLAYBACK_TOKEN_AUDIENCE,
		});
		if (result.ok && result.claims && scopedTo(result.claims.gid)) {
			return {
				ok: true,
				setCookie: true,
				gid: pathGid ?? (result.claims.gid ? String(result.claims.gid) : undefined),
				sub: result.claims.sub,
			};
		}
	}

	const cookie = readCookie(request.headers.get("Cookie"), env.SESSION_COOKIE_NAME);
	if (cookie) {
		const result = await verifyHs256(cookie, env.PLAYBACK_TOKEN_SECRET, {
			issuer: env.SESSION_COOKIE_ISSUER,
			audience: env.SESSION_COOKIE_AUDIENCE,
		});
		if (result.ok && result.claims && scopedTo(result.claims.gid)) {
			return {
				ok: true,
				setCookie: false,
				gid: pathGid ?? (result.claims.gid ? String(result.claims.gid) : undefined),
				sub: result.claims.sub,
			};
		}
	}

	return { ok: false };
}

/** Mint the `Set-Cookie` value for the session cookie that rides every segment fetch. */
async function buildSessionCookie(auth: AuthResult, env: Env): Promise<string> {
	const ttl =
		Number.parseInt(env.SESSION_COOKIE_TTL_SECONDS, 10) || DEFAULT_COOKIE_TTL_SECONDS;
	const issuedAt = nowSeconds();
	const value = await signHs256(
		{
			sub: auth.sub,
			gid: auth.gid,
			iat: issuedAt,
			exp: issuedAt + ttl,
			iss: env.SESSION_COOKIE_ISSUER,
			aud: env.SESSION_COOKIE_AUDIENCE,
		},
		env.PLAYBACK_TOKEN_SECRET,
	);
	// Scope the cookie to the game's path so it only rides that game's segments.
	// SameSite=None; Secure is required for a credentialed cross-origin fetch
	// from the portal origin; localhost is treated as a secure context so this
	// works under `wrangler dev` over http. HttpOnly keeps it out of JS.
	const path = auth.gid ? `/games/${auth.gid}/` : "/";
	return `${env.SESSION_COOKIE_NAME}=${value}; Max-Age=${ttl}; Path=${path}; HttpOnly; Secure; SameSite=None`;
}

/** Parse a single HTTP byte-range into an R2 range, or signal a non-range/invalid header. */
function parseRange(header: string): R2Range | "invalid" {
	const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
	if (!match) {
		return "invalid";
	}
	const [, startText, endText] = match;
	if (startText === "" && endText === "") {
		return "invalid";
	}
	if (startText === "") {
		const suffix = Number.parseInt(endText, 10);
		return suffix > 0 ? { suffix } : "invalid";
	}
	const offset = Number.parseInt(startText, 10);
	if (endText === "") {
		return { offset };
	}
	const end = Number.parseInt(endText, 10);
	return end >= offset ? { offset, length: end - offset + 1 } : "invalid";
}

function applyObjectHeaders(headers: Headers, object: R2Object): void {
	// Copies the stored Content-Type (set by the packaging uploader) and friends.
	object.writeHttpMetadata(headers);
	headers.set("ETag", object.httpEtag);
	headers.set("Accept-Ranges", "bytes");
}

async function serveObject(
	request: Request,
	bucket: R2Bucket,
	key: string,
	base: Headers,
): Promise<Response> {
	if (request.method === "HEAD") {
		const object = await bucket.head(key);
		if (!object) {
			return new Response("Not Found", { status: 404, headers: base });
		}
		const headers = new Headers(base);
		applyObjectHeaders(headers, object);
		headers.set("Content-Length", String(object.size));
		return new Response(null, { status: 200, headers });
	}

	const rangeHeader = request.headers.get("Range");
	const range = rangeHeader ? parseRange(rangeHeader) : null;

	if (range && range !== "invalid") {
		let object: R2ObjectBody | null;
		try {
			object = await bucket.get(key, { range });
		} catch {
			// R2 throws when the range is wholly unsatisfiable (offset past EOF).
			const probe = await bucket.head(key);
			const headers = new Headers(base);
			if (probe) {
				headers.set("Content-Range", `bytes */${probe.size}`);
			}
			return new Response("Range Not Satisfiable", { status: 416, headers });
		}
		if (!object) {
			return new Response("Not Found", { status: 404, headers: base });
		}
		const headers = new Headers(base);
		applyObjectHeaders(headers, object);
		const offset = object.range && "offset" in object.range ? (object.range.offset ?? 0) : 0;
		const length =
			object.range && "length" in object.range && object.range.length != null
				? object.range.length
				: object.size - offset;
		headers.set("Content-Range", `bytes ${offset}-${offset + length - 1}/${object.size}`);
		headers.set("Content-Length", String(length));
		return new Response(object.body, { status: 206, headers });
	}

	const object = await bucket.get(key);
	if (!object) {
		return new Response("Not Found", { status: 404, headers: base });
	}
	const headers = new Headers(base);
	applyObjectHeaders(headers, object);
	headers.set("Content-Length", String(object.size));
	return new Response(object.body, { status: 200, headers });
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const url = new URL(request.url);
		const allowedOrigin = resolveAllowedOrigin(
			request.headers.get("Origin"),
			env.ALLOWED_ORIGINS,
		);

		if (request.method === "OPTIONS") {
			return preflightResponse(allowedOrigin);
		}

		const base = corsHeaders(allowedOrigin);

		if (request.method !== "GET" && request.method !== "HEAD") {
			base.set("Allow", "GET, HEAD, OPTIONS");
			return new Response("Method Not Allowed", { status: 405, headers: base });
		}

		const key = decodeURIComponent(url.pathname.replace(/^\/+/, ""));
		if (!key) {
			return new Response("Not Found", { status: 404, headers: base });
		}

		// Enforce the gate before touching R2 so unauthorized requests never see
		// whether an object exists, and serve no media (AC: 403, no media).
		const auth = await authorize(request, url, env);
		if (!auth.ok) {
			return new Response("Forbidden", { status: 403, headers: base });
		}

		if (auth.setCookie) {
			base.append("Set-Cookie", await buildSessionCookie(auth, env));
		}

		return serveObject(request, env.BUCKET, key, base);
	},
} satisfies ExportedHandler<Env>;
