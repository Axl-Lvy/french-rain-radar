package eu.yourname.radar.data

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.parameter
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.datetime.Clock
import kotlin.time.Duration.Companion.minutes
import kotlin.time.Duration.Companion.seconds

/**
 * Polls the backend manifest and emits each fresh copy.
 *
 * The backend writes `manifest.json` atomically every ~5 min as new frames
 * arrive; polling more frequently than that is wasted work but harmless.
 *
 * Two robustness measures keep the client's time scale fresh:
 *
 * 1. Each fetch carries a `?t=<epoch ms>` query param and a `Cache-Control:
 *    no-cache` request header so neither the browser HTTP cache, a CDN, nor
 *    any intermediate proxy can return a stale copy — the slider span is
 *    derived purely from manifest frames and would silently freeze on a
 *    cached response.
 * 2. The poll loop is wall-clock anchored: if `delay()` returned too early
 *    (timer drift) or too late (OS suspended the coroutine while the tab
 *    was inactive / device asleep), we re-fetch as soon as real time
 *    crosses the next tick. `MAX_STALENESS` is the hard ceiling: if we
 *    haven't successfully fetched within this window, the next iteration
 *    forces a fetch regardless.
 */
class RadarRepository(private val client: HttpClient) {

    suspend fun fetchManifest(): Manifest = client.get("manifest.json") {
        parameter("t", Clock.System.now().toEpochMilliseconds())
        header("Cache-Control", "no-cache")
    }.body()

    fun pollManifest(intervalSeconds: Int = 60): Flow<Manifest> = flow {
        val interval = intervalSeconds.seconds
        var nextTick = Clock.System.now()
        while (true) {
            runCatching { fetchManifest() }
                .onSuccess { emit(it) }
            nextTick += interval
            val now = Clock.System.now()
            val sleep = (nextTick - now).coerceAtMost(MAX_STALENESS)
            if (sleep.isPositive()) delay(sleep) else nextTick = now
        }
    }

    private companion object {
        val MAX_STALENESS = 15.minutes
    }
}
