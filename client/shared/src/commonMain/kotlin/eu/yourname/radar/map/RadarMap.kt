package eu.yourname.radar.map

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import eu.yourname.radar.data.Bbox

/**
 * A map view that displays a single PNG ground overlay covering [bbox].
 *
 * The actual implementation per platform wraps MapLibre:
 * - Android: maplibre-native-android
 * - iOS:     maplibre-native-ios (via cinterop)
 * - Wasm:    maplibre-gl-js (via JS interop)
 */
@Composable
expect fun RadarMap(
    bbox: Bbox,
    overlayUrl: String?,
    modifier: Modifier = Modifier,
)
