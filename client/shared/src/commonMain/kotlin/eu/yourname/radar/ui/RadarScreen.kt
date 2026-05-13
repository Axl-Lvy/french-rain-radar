package eu.yourname.radar.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import eu.yourname.radar.data.Bbox
import eu.yourname.radar.map.RadarMap

@Composable
fun RadarScreen() {
    // Placeholder UI; wire to a ViewModel polling the manifest in Phase 1.
    val aptBbox = Bbox(latMin = 43.6, latMax = 44.2, lonMin = 4.6, lonMax = 5.6)
    Box(modifier = Modifier.fillMaxSize()) {
        RadarMap(bbox = aptBbox, overlayUrl = null, modifier = Modifier.fillMaxSize())
        Column(modifier = Modifier.align(Alignment.BottomCenter).padding(16.dp)) {
            Text("French rain radar — scaffolding")
        }
    }
}
