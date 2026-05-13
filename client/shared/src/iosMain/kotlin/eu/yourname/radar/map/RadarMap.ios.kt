package eu.yourname.radar.map

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import eu.yourname.radar.data.Bbox
import eu.yourname.radar.domain.TimelineFrame

/** Placeholder; iOS wiring is out of scope for Phase 2 (no Mac/Xcode here). */
@Composable
actual fun RadarMap(
    bbox: Bbox,
    frames: List<TimelineFrame>,
    currentIndex: Int,
    tileAuthHeader: String,
    cameraTarget: Pair<Double, Double>?,
    userLocationEnabled: Boolean,
    modifier: Modifier,
) {
    Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text("RadarMap[iOS] — ${frames.getOrNull(currentIndex)?.timestamp ?: "no frame"}")
    }
}
