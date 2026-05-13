package eu.yourname.radar.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import eu.yourname.radar.domain.TimelineFrame
import kotlinx.datetime.Instant
import kotlin.math.abs

/**
 * Time-proportional scrubber across the unified timeline.
 *
 * Slider value is a continuous fraction 0..1 across the time span; on scrub
 * we snap to the closest [TimelineFrame] by timestamp. This makes the gap
 * between 5-min radar frames and 15-min forecast frames feel natural —
 * a unit of slider movement corresponds to a unit of wall-clock time, not
 * a frame index.
 *
 * The background track is drawn in two colours: blue up to [pastBoundary]
 * (observed radar) and orange beyond (predicted nowcast + forecast). The
 * Material slider's own track is set transparent so only the painted bar +
 * the thumb remain visible.
 */
@Composable
fun TimelineScrubber(
    frames: List<TimelineFrame>,
    currentIndex: Int,
    onScrub: (Int) -> Unit,
    pastBoundary: Instant?,
    modifier: Modifier = Modifier,
) {
    if (frames.isEmpty()) return

    val minMs = frames.first().timestamp.toEpochMilliseconds()
    val maxMs = frames.last().timestamp.toEpochMilliseconds()
    val span = (maxMs - minMs).coerceAtLeast(1L)
    val pastFraction: Float = pastBoundary
        ?.let { ((it.toEpochMilliseconds() - minMs).toFloat() / span).coerceIn(0f, 1f) }
        ?: 1f
    val currentFraction =
        ((frames[currentIndex].timestamp.toEpochMilliseconds() - minMs).toFloat() / span).coerceIn(0f, 1f)

    Box(modifier = modifier.fillMaxWidth().height(40.dp)) {
        Canvas(Modifier.fillMaxWidth().height(40.dp).align(Alignment.Center)) {
            val trackH = 6.dp.toPx()
            val midY = size.height / 2f - trackH / 2f
            val pastWidthPx = size.width * pastFraction
            drawRect(
                color = PAST_COLOR.copy(alpha = 0.85f),
                topLeft = Offset(0f, midY),
                size = Size(pastWidthPx, trackH),
            )
            drawRect(
                color = FUTURE_COLOR.copy(alpha = 0.85f),
                topLeft = Offset(pastWidthPx, midY),
                size = Size(size.width - pastWidthPx, trackH),
            )
        }
        Slider(
            value = currentFraction,
            onValueChange = { fraction ->
                val targetMs = minMs + (fraction.coerceIn(0f, 1f) * span).toLong()
                val closest = frames.indices.minByOrNull { i ->
                    abs(frames[i].timestamp.toEpochMilliseconds() - targetMs)
                } ?: 0
                onScrub(closest)
            },
            valueRange = 0f..1f,
            colors = SliderDefaults.colors(
                activeTrackColor = Color.Transparent,
                inactiveTrackColor = Color.Transparent,
                activeTickColor = Color.Transparent,
                inactiveTickColor = Color.Transparent,
            ),
            modifier = Modifier.fillMaxWidth().align(Alignment.Center),
        )
    }
}
