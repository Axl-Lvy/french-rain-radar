package eu.yourname.radar.data

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.get
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlin.time.Duration.Companion.seconds

/**
 * Polls the backend manifest and emits each fresh copy.
 *
 * The backend writes `manifest.json` atomically every ~5 min as new frames
 * arrive; polling more frequently than that is wasted work but harmless.
 */
class RadarRepository(private val client: HttpClient) {

    suspend fun fetchManifest(): Manifest = client.get("manifest.json").body()

    fun pollManifest(intervalSeconds: Int = 60): Flow<Manifest> = flow {
        while (true) {
            runCatching { fetchManifest() }
                .onSuccess { emit(it) }
            delay(intervalSeconds.seconds)
        }
    }
}
