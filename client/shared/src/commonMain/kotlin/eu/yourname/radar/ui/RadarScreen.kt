package eu.yourname.radar.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import eu.yourname.radar.Config
import eu.yourname.radar.data.BackendConfig
import eu.yourname.radar.data.Bbox
import eu.yourname.radar.data.FrameKind
import eu.yourname.radar.data.Manifest
import eu.yourname.radar.data.RadarHttpClient
import eu.yourname.radar.data.RadarRepository
import eu.yourname.radar.domain.TimelineFrame
import eu.yourname.radar.domain.toTimeline
import eu.yourname.radar.map.RadarMap
import eu.yourname.radar.settings.SettingsKeys
import eu.yourname.radar.settings.SettingsStore
import io.ktor.client.HttpClient
import kotlinx.datetime.Instant
import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime
import kotlin.io.encoding.Base64
import kotlin.io.encoding.ExperimentalEncodingApi

@Composable
fun RadarScreen(settings: SettingsStore) {
    var username by remember { mutableStateOf(settings.getString(SettingsKeys.USERNAME)) }
    var password by remember { mutableStateOf(settings.getString(SettingsKeys.PASSWORD)) }

    val creds = remember(username, password) {
        val u = username
        val p = password
        if (!u.isNullOrBlank() && !p.isNullOrEmpty()) {
            BackendConfig(baseUrl = Config.BASE_URL, username = u, password = p)
        } else null
    }

    if (creds == null) {
        AuthGate(initialUsername = username.orEmpty()) { u, p ->
            settings.putString(SettingsKeys.USERNAME, u)
            settings.putString(SettingsKeys.PASSWORD, p)
            username = u
            password = p
        }
        return
    }

    val httpClient: HttpClient = remember(creds) { RadarHttpClient.create(creds) }
    DisposableEffect(httpClient) { onDispose { httpClient.close() } }
    val repo = remember(httpClient) { RadarRepository(httpClient) }

    @OptIn(ExperimentalEncodingApi::class)
    val tileAuthHeader = remember(creds) {
        "Basic " + Base64.encode("${creds.username}:${creds.password}".encodeToByteArray())
    }

    var manifest by remember { mutableStateOf<Manifest?>(null) }
    LaunchedEffect(repo) {
        repo.pollManifest(intervalSeconds = 60).collect { manifest = it }
    }

    val timeline: List<TimelineFrame> = remember(manifest) {
        manifest?.toTimeline(Config.BASE_URL) ?: emptyList()
    }
    val bbox: Bbox = manifest?.bbox ?: FRANCE_BBOX

    var currentIndex by remember { mutableStateOf(-1) }
    LaunchedEffect(timeline) {
        when {
            currentIndex < 0 && timeline.isNotEmpty() -> currentIndex = timeline.lastIndex
            currentIndex >= timeline.size -> currentIndex = (timeline.size - 1).coerceAtLeast(0)
        }
    }

    val currentFrame = timeline.getOrNull(currentIndex)
    var cameraTarget by remember { mutableStateOf<Pair<Double, Double>?>(null) }
    var userLocationEnabled by remember { mutableStateOf(false) }

    // Divider between observed (radar) and predicted (nowcast + forecast)
    // — used to colour the slider track.
    val latestRadarTime: Instant? = remember(timeline) {
        timeline.filter { it.kind == FrameKind.RADAR }.maxOfOrNull { it.timestamp }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        RadarMap(
            bbox = bbox,
            frames = timeline,
            currentIndex = currentIndex.coerceAtLeast(0),
            tileAuthHeader = tileAuthHeader,
            cameraTarget = cameraTarget,
            userLocationEnabled = userLocationEnabled,
            modifier = Modifier.fillMaxSize(),
        )

        if (manifest == null) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        }

        if (currentFrame != null) {
            BottomTimelineCard(
                frames = timeline,
                currentIndex = currentIndex,
                onScrub = { currentIndex = it },
                pastBoundary = latestRadarTime,
                modifier = Modifier.align(Alignment.BottomCenter).padding(12.dp),
            )
        }

        LocationFab(
            onLocate = { lat, lon ->
                cameraTarget = lat to lon
                userLocationEnabled = true
            },
            modifier = Modifier.align(Alignment.BottomEnd).padding(end = 16.dp, bottom = 184.dp),
        )
    }
}

@Composable
private fun AuthGate(
    initialUsername: String,
    onSubmit: (String, String) -> Unit,
) {
    Surface(Modifier.fillMaxSize()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            AuthSheet(onSubmit = onSubmit, initialUsername = initialUsername)
        }
    }
}

@Composable
private fun BottomTimelineCard(
    frames: List<TimelineFrame>,
    currentIndex: Int,
    onScrub: (Int) -> Unit,
    pastBoundary: Instant?,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors().copy(
            containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f),
        ),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            val current = frames[currentIndex]
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    text = formatLocalTime(current.timestamp),
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                KindChip(current.kind)
            }
            TimelineScrubber(
                frames = frames,
                currentIndex = currentIndex,
                onScrub = onScrub,
                pastBoundary = pastBoundary,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun KindChip(kind: FrameKind) {
    val (label, tint) = when (kind) {
        FrameKind.RADAR -> "radar" to PAST_COLOR
        FrameKind.NOWCAST -> "nowcast" to NOWCAST_COLOR
        FrameKind.FORECAST -> "forecast" to FUTURE_COLOR
    }
    AssistChip(
        onClick = {},
        label = { Text(label) },
        colors = AssistChipDefaults.assistChipColors().copy(labelColor = tint),
    )
}

private fun formatLocalTime(instant: Instant): String {
    val ldt = instant.toLocalDateTime(TimeZone.currentSystemDefault())
    val hh = ldt.hour.toString().padStart(2, '0')
    val mm = ldt.minute.toString().padStart(2, '0')
    return "$hh:$mm"
}

internal val PAST_COLOR = Color(0xFF4C8BD9)     // blue — observed radar
internal val NOWCAST_COLOR = Color(0xFF9C5DD9)  // purple — short-range prediction
internal val FUTURE_COLOR = Color(0xFFE8923C)   // orange — AROME-PI forecast

/** Metropolitan France + Corsica fallback bbox if the manifest hasn't arrived yet. */
private val FRANCE_BBOX = Bbox(latMin = 41.3, latMax = 51.5, lonMin = -5.5, lonMax = 10.0)
