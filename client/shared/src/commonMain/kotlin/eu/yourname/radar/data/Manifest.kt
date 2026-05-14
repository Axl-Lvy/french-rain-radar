package eu.yourname.radar.data

import kotlinx.datetime.Instant
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Kotlin mirror of `schema/manifest.schema.json` (v2: lazy XYZ tile pyramid).
 *
 * The `ManifestSchemaConsistencyTest` in `commonTest` decodes the example
 * `schema/examples/manifest.example.json` against these classes; if it fails,
 * the schema and the Kotlin model have drifted.
 */
@Serializable
data class Manifest(
    val manifestVersion: Int,
    val bbox: Bbox,
    val colorScale: String? = null,
    val layers: Layers,
)
// Note: the schema's `generatedAt` is intentionally not modelled here.
// The backend writes it with microsecond precision (e.g. ".327681Z"); Kotlin/Wasm's
// kotlinx-datetime Instant parser rejects sub-millisecond fractional seconds and
// throws, which `pollManifest`'s runCatching silently swallows — leaving the UI
// stuck on its loading spinner. `ignoreUnknownKeys = true` lets the field exist
// in the JSON without being decoded.

@Serializable
data class Bbox(
    val latMin: Double,
    val latMax: Double,
    val lonMin: Double,
    val lonMax: Double,
)

@Serializable
data class Layers(
    val radar: Layer? = null,
    val nowcast: Layer? = null,
    val forecast: Layer? = null,
)

@Serializable
data class Layer(
    /** Template with `{timestamp}`/`{z}`/`{x}`/`{y}` placeholders. */
    val tileUrlTemplate: String,
    val minZoom: Int,
    val maxZoom: Int,
    /** Reference time of the NWP run (forecast only). */
    val runTime: Instant? = null,
    val frames: List<Frame>,
)

@Serializable
data class Frame(val timestamp: Instant)

enum class FrameKind {
    @SerialName("radar")    RADAR,
    @SerialName("nowcast")  NOWCAST,
    @SerialName("forecast") FORECAST,
}
