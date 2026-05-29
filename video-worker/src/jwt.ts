// Minimal HS256 JWT sign/verify on the Web Crypto API (no dependencies).
//
// The playback API (gam.playback.tokens, TGF-360) mints HS256 JWTs with PyJWT;
// this Worker must verify them with the identical secret, algorithm, issuer,
// and audience. Keeping the implementation tiny and dependency-free keeps the
// Worker's cold start and bundle minimal, which matches ADR-0008's "validate
// in-Worker, no external call" requirement. The same machinery also signs the
// longer-lived session cookie the Worker hands back after a token exchange.

export interface JwtClaims {
	sub?: string;
	gid?: string;
	iat?: number;
	exp?: number;
	iss?: string;
	aud?: string | string[];
	[key: string]: unknown;
}

export interface VerifyResult {
	ok: boolean;
	claims?: JwtClaims;
	/** Machine-readable failure reason; useful in tests/logs, never sent to clients. */
	reason?: string;
}

export interface VerifyOptions {
	issuer?: string;
	audience?: string;
	/** UNIX seconds; defaults to the current time. Overridable for deterministic tests. */
	now?: number;
}

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function base64UrlEncode(bytes: Uint8Array): string {
	let binary = "";
	for (const byte of bytes) {
		binary += String.fromCharCode(byte);
	}
	return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlDecode(value: string): Uint8Array {
	const padded = value + "=".repeat((4 - (value.length % 4)) % 4);
	const binary = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) {
		bytes[i] = binary.charCodeAt(i);
	}
	return bytes;
}

function encodeSegment(value: object): string {
	return base64UrlEncode(encoder.encode(JSON.stringify(value)));
}

async function importKey(
	secret: string,
	usage: "sign" | "verify",
): Promise<CryptoKey> {
	return crypto.subtle.importKey(
		"raw",
		encoder.encode(secret),
		{ name: "HMAC", hash: "SHA-256" },
		false,
		[usage],
	);
}

/** Sign `claims` as an HS256 JWT. Mirrors PyJWT's default header. */
export async function signHs256(claims: JwtClaims, secret: string): Promise<string> {
	const header = encodeSegment({ alg: "HS256", typ: "JWT" });
	const payload = encodeSegment(claims);
	const signingInput = `${header}.${payload}`;
	const key = await importKey(secret, "sign");
	const signature = new Uint8Array(
		await crypto.subtle.sign("HMAC", key, encoder.encode(signingInput)),
	);
	return `${signingInput}.${base64UrlEncode(signature)}`;
}

/** Verify an HS256 JWT's signature and registered claims (exp, iss, aud). */
export async function verifyHs256(
	token: string,
	secret: string,
	options: VerifyOptions = {},
): Promise<VerifyResult> {
	const parts = token.split(".");
	if (parts.length !== 3) {
		return { ok: false, reason: "malformed" };
	}
	const [header, payload, signature] = parts;

	let valid: boolean;
	try {
		const key = await importKey(secret, "verify");
		valid = await crypto.subtle.verify(
			"HMAC",
			key,
			base64UrlDecode(signature),
			encoder.encode(`${header}.${payload}`),
		);
	} catch {
		return { ok: false, reason: "signature" };
	}
	if (!valid) {
		return { ok: false, reason: "signature" };
	}

	let claims: JwtClaims;
	try {
		claims = JSON.parse(decoder.decode(base64UrlDecode(payload)));
	} catch {
		return { ok: false, reason: "payload" };
	}

	const now = options.now ?? Math.floor(Date.now() / 1000);
	if (typeof claims.exp !== "number" || now >= claims.exp) {
		return { ok: false, reason: "expired" };
	}
	if (options.issuer && claims.iss !== options.issuer) {
		return { ok: false, reason: "issuer" };
	}
	if (options.audience) {
		const aud = claims.aud;
		const matches = Array.isArray(aud)
			? aud.includes(options.audience)
			: aud === options.audience;
		if (!matches) {
			return { ok: false, reason: "audience" };
		}
	}

	return { ok: true, claims };
}
