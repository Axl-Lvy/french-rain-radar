package eu.yourname.radar.map

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import eu.yourname.radar.data.Bbox
import eu.yourname.radar.domain.TimelineFrame

/**
 * Pan/zoom map showing one frame at a time from the unified radar timeline.
 *
 * Each frame gets its own MapLibre `RasterSource` + `RasterLayer`, all added
 * up-front. Scrubbing toggles `raster-opacity` between 0.75 (active) and 0
 * (hidden) — no `setTiles` round-trip, no re-fetch. MapLibre lazily fetches
 * each layer's tiles when first visible in the viewport and keeps them
 * cached in memory.
 *
 * [tileAuthHeader] is the full ``Authorization: Basic …`` value injected on
 * every backend tile fetch. [cameraTarget] is a (lat, lon) pair — changing
 * it flies the camera there. [userLocationEnabled] turns on the platform's
 * native blue-dot user-position renderer once the user has granted location
 * permission. [bbox] clamps panning + initial fit.
 */
@Composable
expect fun RadarMap(
    bbox: Bbox,
    frames: List<TimelineFrame>,
    currentIndex: Int,
    tileAuthHeader: String,
    cameraTarget: Pair<Double, Double>?,
    userLocationEnabled: Boolean,
    modifier: Modifier = Modifier,
)
