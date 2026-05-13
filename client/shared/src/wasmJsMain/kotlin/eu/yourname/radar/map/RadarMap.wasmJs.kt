package eu.yourname.radar.map

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import eu.yourname.radar.data.Bbox

/**
 * TODO: replace placeholder with an HTMLElement hosting a `<div>` that mounts
 * maplibre-gl-js (loaded from a <script> tag in index.html).
 *
 * Compose Multiplatform for Wasm exposes an HTML escape hatch; until this is
 * implemented, the placeholder lets the rest of the app compile and run.
 */
@Composable
actual fun RadarMap(bbox: Bbox, overlayUrl: String?, modifier: Modifier) {
    Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text("RadarMap[Wasm] — overlay=$overlayUrl")
    }
}
