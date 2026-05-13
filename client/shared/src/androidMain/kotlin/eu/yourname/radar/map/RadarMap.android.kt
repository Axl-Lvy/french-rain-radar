package eu.yourname.radar.map

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import eu.yourname.radar.data.Bbox

/**
 * TODO: replace the placeholder with a real MapLibre `MapView`.
 *
 * Implementation sketch:
 *   AndroidView(factory = { ctx ->
 *       MapView(ctx).apply { getMapAsync { map ->
 *           map.setStyle(Style.Builder().fromUri("https://demotiles.maplibre.org/style.json"))
 *           map.setLatLngBoundsForCameraTarget(LatLngBounds.from(bbox.latMax, bbox.lonMax, bbox.latMin, bbox.lonMin))
 *           // ImageSource("radar", bounds, bitmap) + RasterLayer to overlay the PNG
 *       }}
 *   })
 */
@Composable
actual fun RadarMap(bbox: Bbox, overlayUrl: String?, modifier: Modifier) {
    Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text("RadarMap[Android] — overlay=$overlayUrl")
    }
}
