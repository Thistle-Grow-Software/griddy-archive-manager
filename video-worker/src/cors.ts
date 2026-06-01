// CORS for credentialed cross-origin playback (ADR-0008).
//
// Segment fetches carry the session cookie, so they are credentialed requests:
// the spec forbids a wildcard `Access-Control-Allow-Origin` and requires
// `Access-Control-Allow-Credentials: true`. We therefore echo back the request
// Origin only when it is on the configured allowlist, and never emit `*`. The
// exposed headers are exactly what hls.js / the browser need to drive HLS range
// scrubbing (Content-Range, Accept-Ranges, Content-Length, ETag).

const ALLOW_METHODS = "GET, HEAD, OPTIONS";
const ALLOW_HEADERS = "Range, Content-Type";
const EXPOSE_HEADERS = "Content-Length, Content-Range, Accept-Ranges, ETag";
const MAX_AGE = "86400";

/** Return the Origin to echo if it is allowed, else null. */
export function resolveAllowedOrigin(
	requestOrigin: string | null,
	allowedCsv: string,
): string | null {
	if (!requestOrigin) {
		return null;
	}
	const allowed = allowedCsv
		.split(",")
		.map((value) => value.trim())
		.filter(Boolean);
	return allowed.includes(requestOrigin) ? requestOrigin : null;
}

/** Base CORS headers applied to every actual (non-preflight) response. */
export function corsHeaders(allowedOrigin: string | null): Headers {
	const headers = new Headers();
	// Responses vary by Origin since the allowed value is echoed per request.
	headers.set("Vary", "Origin");
	if (allowedOrigin) {
		headers.set("Access-Control-Allow-Origin", allowedOrigin);
		headers.set("Access-Control-Allow-Credentials", "true");
		headers.set("Access-Control-Expose-Headers", EXPOSE_HEADERS);
	}
	return headers;
}

/** Preflight (OPTIONS) response advertising the methods/headers we allow. */
export function preflightResponse(allowedOrigin: string | null): Response {
	const headers = corsHeaders(allowedOrigin);
	if (allowedOrigin) {
		headers.set("Access-Control-Allow-Methods", ALLOW_METHODS);
		headers.set("Access-Control-Allow-Headers", ALLOW_HEADERS);
		headers.set("Access-Control-Max-Age", MAX_AGE);
	}
	return new Response(null, { status: 204, headers });
}
