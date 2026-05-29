import type { Env } from "../src/index";

// Type the `env` exposed by `cloudflare:test` as the Worker's own Env, so tests
// get the BUCKET binding and config vars fully typed.
declare module "cloudflare:test" {
	interface ProvidedEnv extends Env {}
}
