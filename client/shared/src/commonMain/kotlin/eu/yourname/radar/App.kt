package eu.yourname.radar

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import eu.yourname.radar.ui.RadarScreen

@Composable
fun App() {
    MaterialTheme {
        Surface { RadarScreen() }
    }
}
