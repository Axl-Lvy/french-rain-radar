package eu.yourname.radar.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/**
 * "Centre on my location" floating action button.
 *
 * Each platform handles the permission flow + location lookup natively. On
 * success it invokes [onLocate] with `(lat, lon)`, which the screen forwards
 * to `RadarMap.cameraTarget` so the camera flies there.
 *
 * On the Web target this is a no-op composable — the map uses
 * `maplibregl.GeolocateControl`, which renders its own button inside the
 * map. Rendering a second one in Compose would be confusing.
 */
@Composable
expect fun LocationFab(
    onLocate: (lat: Double, lon: Double) -> Unit,
    modifier: Modifier = Modifier,
)
