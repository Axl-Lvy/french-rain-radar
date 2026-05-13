package eu.yourname.radar.domain

import eu.yourname.radar.data.FrameKind
import eu.yourname.radar.data.Manifest

/** Flattens the manifest's three layers into a single chronological timeline. */
fun Manifest.toTimeline(baseUrl: String): List<TimelineFrame> {
    val base = baseUrl.trimEnd('/')
    val out = buildList {
        layers.radar?.frames?.forEach { add(TimelineFrame(it.timestamp, "$base/${it.url}", FrameKind.RADAR)) }
        layers.nowcast?.frames?.forEach { add(TimelineFrame(it.timestamp, "$base/${it.url}", FrameKind.NOWCAST)) }
        layers.forecast?.frames?.forEach { add(TimelineFrame(it.timestamp, "$base/${it.url}", FrameKind.FORECAST)) }
    }
    return out.sortedBy { it.timestamp }
}
