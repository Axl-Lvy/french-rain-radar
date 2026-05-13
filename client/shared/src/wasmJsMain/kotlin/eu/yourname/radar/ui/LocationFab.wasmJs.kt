package eu.yourname.radar.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/**
 * Web target uses `maplibregl.GeolocateControl` (added in
 * `RadarMap.wasmJs.kt`), which provides its own button inside the map.
 * Compose draws nothing here.
 */
@Composable
actual fun LocationFab(
    onLocate: (lat: Double, lon: Double) -> Unit,
    modifier: Modifier,
) {
    Box(modifier = modifier)
}
