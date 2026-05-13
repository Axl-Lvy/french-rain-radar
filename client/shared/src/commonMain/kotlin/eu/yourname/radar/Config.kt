package eu.yourname.radar

/**
 * Build-time configuration baked into the client. Edit and rebuild to point
 * at a different backend.
 *
 * The Caddyfile on the production VPS serves the manifest at `/manifest.json`,
 * tiles at `/{layer}/{timestamp}/{z}/{x}/{y}.png`, and gates everything behind
 * HTTP Basic auth + a per-user rate limit. The trailing slash is significant
 * — Ktor's [io.ktor.client.plugins.defaultRequest] treats the URL as a base
 * to resolve relative paths against.
 */
object Config {
    const val BASE_URL: String = "https://rain.axl-lvy.fr/"
}
