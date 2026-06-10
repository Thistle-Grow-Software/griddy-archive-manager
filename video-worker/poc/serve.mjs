// Tiny static server for the PoC player page (ADR-0008, TGF-363).
//
// The player must be served from an origin on the Worker's ALLOWED_ORIGINS list
// (http://localhost:5173 — Vite's default, which the portal will use), because
// the segment fetches are *credentialed* cross-origin requests to the Worker on
// :8787 and the Worker only echoes Access-Control-Allow-Origin for allowlisted
// origins. This server has one job: hand out poc/player.html and the bundled
// hls.js (mapped from node_modules so the PoC is fully offline — no CDN).
//
// Playwright starts this via its `webServer` config; a human runs it with
// `node poc/serve.mjs` (see the runbook).

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join, normalize } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = here; // serves files under poc/
const hlsDist = join(here, "..", "node_modules", "hls.js", "dist", "hls.min.js");
const PORT = Number.parseInt(process.env.POC_PLAYER_PORT ?? "5173", 10);

const TYPES = {
	".html": "text/html; charset=utf-8",
	".js": "text/javascript; charset=utf-8",
	".css": "text/css; charset=utf-8",
};

const server = createServer(async (req, res) => {
	try {
		const url = new URL(req.url, `http://localhost:${PORT}`);
		let path = decodeURIComponent(url.pathname);
		if (path === "/") path = "/player.html";

		// hls.js lives outside poc/; map an explicit vendor path to it.
		let filePath;
		if (path === "/vendor/hls.min.js") {
			filePath = hlsDist;
		} else {
			// Contain the resolved path under root (no path traversal).
			const resolved = normalize(join(root, path));
			if (!resolved.startsWith(root)) {
				res.writeHead(403).end("Forbidden");
				return;
			}
			filePath = resolved;
		}

		const body = await readFile(filePath);
		const ext = filePath.slice(filePath.lastIndexOf("."));
		res.writeHead(200, {
			"Content-Type": TYPES[ext] ?? "application/octet-stream",
			"Cache-Control": "no-store",
		});
		res.end(body);
	} catch {
		res.writeHead(404).end("Not Found");
	}
});

server.listen(PORT, () => {
	process.stdout.write(`PoC player server on http://localhost:${PORT}\n`);
});
