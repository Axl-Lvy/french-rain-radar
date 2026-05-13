package eu.yourname.radar.data

import kotlinx.datetime.Instant
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Kotlin mirror of `schema/manifest.schema.json`.
 *
 * The `ManifestSchemaConsistencyTest` in `commonTest` decodes the example
 * `schema/examples/manifest.example.json` against these classes; if it fails,
 * the schema and the Kotlin model have drifted.
 */
@Serializable
data class Manifest(
    val manifestVersion: Int,
    val generatedAt: Instant,
    val bbox: Bbox,
    val tileSize: TileSize,
    val colorScale: String? = null,
    val layers: Layers,
)

@Serializable
data class Bbox(
    val latMin: Double,
    val latMax: Double,
    val lonMin: Double,
    val lonMax: Double,
)

@Serializable
data class TileSize(val width: Int, val height: Int)

@Serializable
data class Layers(
    val radar: Layer? = null,
    val nowcast: Layer? = null,
    val forecast: Layer? = null,
)

@Serializable
data class Layer(
    val frames: List<Frame>,
    /** Reference time of the NWP run that produced this layer's frames (forecast only). */
    val runTime: Instant? = null,
)

@Serializable
data class Frame(
    val timestamp: Instant,
    val url: String,
)

/** Kind of a frame, used by the UI to label them on the timeline. */
enum class FrameKind {
    @SerialName("radar")    RADAR,
    @SerialName("nowcast")  NOWCAST,
    @SerialName("forecast") FORECAST,
}
