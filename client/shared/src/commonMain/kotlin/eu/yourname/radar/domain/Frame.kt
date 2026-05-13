package eu.yourname.radar.domain

import eu.yourname.radar.data.FrameKind
import kotlinx.datetime.Instant

/** A frame on the unified timeline (radar history + nowcast + forecast). */
data class TimelineFrame(
    val timestamp: Instant,
    val absoluteUrl: String,
    val kind: FrameKind,
)
