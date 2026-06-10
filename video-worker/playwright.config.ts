import { defineConfig, devices } from "@playwright/test";

// Playwright end-to-end PoC for ADR-0008 / TGF-363: drive a real browser through
// the full token -> Worker -> cookie -> segment chain against a packaged game in
// the local Miniflare R2 store. Two real engines run automatically — Chromium and
// Firefox; Safari (WebKit) stays a documented manual step because WebKit on Linux
// does not reliably decode the catalog's H.264/AAC in MSE (see poc/runbook.md).
//
// Two servers are brought up for the run:
//   * wrangler dev on :8787 — the Worker bound to the local R2 (the same store
//     `manage.py poc_load_game` loaded the game into).
//   * poc/serve.mjs on :5173 — serves the hls.js player from an allowlisted
//     origin so the credentialed cross-origin segment fetches are CORS-legal.
export default defineConfig({
	testDir: "poc",
	testMatch: /playback\.spec\.ts$/,
	// Playback + buffering over real segments is not instant; give each step room
	// but keep the whole run bounded.
	timeout: 60_000,
	expect: { timeout: 20_000 },
	fullyParallel: false,
	workers: 1,
	reporter: [["list"], ["html", { open: "never", outputFolder: "poc/playwright-report" }]],
	use: {
		baseURL: "http://localhost:5173",
		trace: "retain-on-failure",
		video: "retain-on-failure",
	},
	projects: [
		{ name: "chromium", use: { ...devices["Desktop Chrome"] } },
		{ name: "firefox", use: { ...devices["Desktop Firefox"] } },
	],
	webServer: [
		{
			// `--local` (default in wrangler v4) + the committed .dev.vars secret.
			command: "npx wrangler dev --port 8787",
			url: "http://localhost:8787/",
			reuseExistingServer: !process.env.CI,
			timeout: 120_000,
			stdout: "pipe",
			stderr: "pipe",
		},
		{
			command: "node poc/serve.mjs",
			url: "http://localhost:5173/player.html",
			reuseExistingServer: !process.env.CI,
			timeout: 30_000,
		},
	],
});
