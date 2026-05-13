package eu.yourname.radar.map

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import eu.yourname.radar.data.Bbox

/**
 * TODO: replace placeholder with a `UIKitView` hosting `MGLMapView` from MapLibre iOS.
 *
 * The cinterop bindings for MapLibre iOS live under
 * `shared/src/nativeInterop/cinterop/MapLibre.def`. As an alternative, wrap
 * MapLibre in a thin Swift Package and call it via objc-names.
 */
@Composable
actual fun RadarMap(bbox: Bbox, overlayUrl: String?, modifier: Modifier) {
    Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text("RadarMap[iOS] — overlay=$overlayUrl")
    }
}
