package eu.yourname.radar

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import eu.yourname.radar.settings.SettingsStore
import eu.yourname.radar.ui.RadarScreen

/**
 * App root. Each platform entry-point (MainActivity, wasmJsApp Main, iOS
 * MainViewController) constructs a [SettingsStore] (Android additionally
 * binds it to an application context) and passes it here.
 */
@Composable
fun App(settings: SettingsStore) {
    MaterialTheme {
        Surface { RadarScreen(settings) }
    }
}
