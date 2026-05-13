package eu.yourname.radar.domain

import eu.yourname.radar.data.FrameKind
import eu.yourname.radar.data.Layer
import eu.yourname.radar.data.Manifest

/**
 * Flattens the manifest's three layers into a single chronological timeline,
 * preferring the highest-fidelity source for any given timestamp:
 * `radar > nowcast > forecast`. Nowcast frames whose timestamp is already
 * covered by radar are dropped; forecast frames whose timestamp is already
 * covered by radar OR nowcast are dropped.
 *
 * Without this dedup, AROME-PI forecast frames published over the past hour
 * would appear at the same wall-clock times as their corresponding radar
 * observations — the scrubber would jump between "forecast 22:15" and
 * "radar 22:15" for the same minute, which is confusing.
 *
 * [baseUrl] is the backend origin (e.g. `https://rain.example.tld`). The
 * resulting [TimelineFrame.tileUrlTemplate] has `{timestamp}` already
 * substituted; only `{z}/{x}/{y}` remain for MapLibre to fill per tile.
 */
fun Manifest.toTimeline(baseUrl: String): List<TimelineFrame> {
    val base = baseUrl.trimEnd('/')
    val radar = layers.radar?.toFrames(base, FrameKind.RADAR).orEmpty()
    val nowcast = layers.nowcast?.toFrames(base, FrameKind.NOWCAST).orEmpty()
    val forecast = layers.forecast?.toFrames(base, FrameKind.FORECAST).orEmpty()

    val latestRadar = radar.maxOfOrNull { it.timestamp }
    val keptNowcast = if (latestRadar != null) nowcast.filter { it.timestamp > latestRadar } else nowcast
    val latestPredicted = keptNowcast.maxOfOrNull { it.timestamp } ?: latestRadar
    val keptForecast = if (latestPredicted != null) forecast.filter { it.timestamp > latestPredicted } else forecast

    return (radar + keptNowcast + keptForecast).sortedBy { it.timestamp }
}

private fun Layer.toFrames(base: String, kind: FrameKind): List<TimelineFrame> =
    frames.map { frame ->
        TimelineFrame(
            timestamp = frame.timestamp,
            kind = kind,
            tileUrlTemplate = "$base/${tileUrlTemplate.replace("{timestamp}", frame.timestamp.toUrlSafe())}",
            minZoom = minZoom,
            maxZoom = maxZoom,
        )
    }

/**
 * The backend stores source files and tile cache dirs under the URL-safe form
 * `YYYY-MM-DDTHH-MM-SSZ` (colons replaced with dashes). The tile route on the
 * server uses the same form, so we must substitute it — not the ISO form — into
 * the template.
 */
internal fun kotlinx.datetime.Instant.toUrlSafe(): String =
    toString().replace(':', '-')
