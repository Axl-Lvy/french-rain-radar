package eu.yourname.radar.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/** iOS is out of scope for Phase 2; this stays a no-op until the actuals land. */
@Composable
actual fun LocationFab(
    onLocate: (lat: Double, lon: Double) -> Unit,
    modifier: Modifier,
) {
    Box(modifier = modifier)
}
