package eu.yourname.radar.ui

import androidx.compose.foundation.layout.Row
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

@Composable
fun PlaybackControls(
    playing: Boolean,
    onTogglePlay: () -> Unit,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(modifier = modifier) {
        Button(onClick = onPrev) { Text("⏮") }
        Button(onClick = onTogglePlay) { Text(if (playing) "⏸" else "▶") }
        Button(onClick = onNext) { Text("⏭") }
    }
}
