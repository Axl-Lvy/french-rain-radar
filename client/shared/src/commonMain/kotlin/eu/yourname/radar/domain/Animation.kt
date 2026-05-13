package eu.yourname.radar.domain

import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds

/**
 * Drives the playback cursor across a timeline.
 *
 * Loops back to the start after a brief pause when the end is reached.
 */
fun playback(
    frameCount: Int,
    frameDuration: Duration = 300.milliseconds,
    holdAtEnd: Duration = 1500.milliseconds,
    startIndex: Int = 0,
): Flow<Int> = flow {
    if (frameCount == 0) return@flow
    var i = startIndex.coerceIn(0, frameCount - 1)
    while (true) {
        emit(i)
        val atEnd = i == frameCount - 1
        delay(if (atEnd) holdAtEnd else frameDuration)
        i = (i + 1) % frameCount
    }
}
