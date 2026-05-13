package eu.yourname.radar.domain

import eu.yourname.radar.data.FrameKind
import kotlinx.datetime.Instant

/**
 * A frame on the unified timeline (radar history + nowcast + forecast).
 *
 * For v2 lazy tiles, frames don't carry per-frame URLs — clients substitute
 * [timestamp] into the layer's `tileUrlTemplate` and let MapLibre fill
 * `{z}/{x}/{y}`.
 */
data class TimelineFrame(
    val timestamp: Instant,
    val kind: FrameKind,
    /** Layer's `tileUrlTemplate` with `{timestamp}` already substituted. */
    val tileUrlTemplate: String,
    val minZoom: Int,
    val maxZoom: Int,
) {
    /**
     * Stable identifier for the MapLibre source/layer corresponding to this
     * frame. Must be unique across the timeline; used by the per-platform
     * map actuals to add one source/layer per frame and toggle opacity
     * on scrub.
     */
    val layerId: String
        get() = "radar-${kind.name.lowercase()}-${timestamp.toString().replace(':', '-')}"
}
