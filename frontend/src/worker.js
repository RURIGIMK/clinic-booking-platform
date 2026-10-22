/**
 * Minimal Worker entry point for the Vite-built single-page application.
 * Cloudflare serves files from the configured ASSETS binding and applies
 * the SPA fallback configured in wrangler.jsonc.
 */
export default {
  fetch(request, env) {
    return env.ASSETS.fetch(request);
  },
};
