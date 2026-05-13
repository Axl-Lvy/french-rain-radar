package eu.yourname.radar.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import eu.yourname.radar.domain.TimelineFrame

@Composable
fun TimelineScrubber(
    frames: List<TimelineFrame>,
    currentIndex: Int,
    onScrub: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (frames.isEmpty()) return
    Column(modifier = modifier.fillMaxWidth().padding(16.dp)) {
        Text(frames[currentIndex].timestamp.toString())
        Slider(
            value = currentIndex.toFloat(),
            onValueChange = { onScrub(it.toInt().coerceIn(0, frames.lastIndex)) },
            valueRange = 0f..(frames.lastIndex).coerceAtLeast(0).toFloat(),
            steps = (frames.size - 2).coerceAtLeast(0),
        )
    }
}
