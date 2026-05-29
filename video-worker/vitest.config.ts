import { defineWorkersConfig } from "@cloudflare/vitest-pool-workers/config";

// Runs the test suite inside workerd against the real Worker, with BUCKET bound
// to an isolated local R2 (Miniflare) — the same shape `wrangler dev` serves.
// PLAYBACK_TOKEN_SECRET is injected as a test-only binding so the suite can mint
// tokens/cookies with the same secret the Worker verifies against, without
// depending on a developer's `.dev.vars`.
export default defineWorkersConfig({
	test: {
		poolOptions: {
			workers: {
				wrangler: { configPath: "./wrangler.jsonc" },
				miniflare: {
					bindings: {
						PLAYBACK_TOKEN_SECRET: "test-secret-do-not-use-in-prod",
					},
				},
			},
		},
	},
});
