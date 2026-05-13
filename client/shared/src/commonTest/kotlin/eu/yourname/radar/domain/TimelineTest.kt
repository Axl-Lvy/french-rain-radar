package eu.yourname.radar.domain

import eu.yourname.radar.data.FrameKind
import eu.yourname.radar.data.Manifest
import eu.yourname.radar.data.RadarHttpClient
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Realistic snapshot: 21:00 AROME-PI run published 21:15/21:30/21:45 leadtimes,
 * radar observed up to 20:55, nowcast predicting 21:00 and 21:05. Forecast
 * frames at 21:15+ are kept (no radar/nowcast coverage there); 21:00 forecast
 * would clash with nowcast and is dropped.
 */
private const val MIXED_MANIFEST = """
{
  "manifestVersion": 2,
  "generatedAt": "2026-05-13T20:57:31Z",
  "bbox": { "latMin": 41.3, "latMax": 51.5, "lonMin": -5.5, "lonMax": 10.0 },
  "colorScale": "rainviewer-original",
  "layers": {
    "radar": {
      "tileUrlTemplate": "radar/{timestamp}/{z}/{x}/{y}.png",
      "minZoom": 5,
      "maxZoom": 10,
      "frames": [
        { "timestamp": "2026-05-13T20:50:00Z" },
        { "timestamp": "2026-05-13T20:55:00Z" }
      ]
    },
    "nowcast": {
      "tileUrlTemplate": "nowcast/{timestamp}/{z}/{x}/{y}.png",
      "minZoom": 5,
      "maxZoom": 10,
      "frames": [
        { "timestamp": "2026-05-13T20:55:00Z" },
        { "timestamp": "2026-05-13T21:00:00Z" },
        { "timestamp": "2026-05-13T21:05:00Z" }
      ]
    },
    "forecast": {
      "tileUrlTemplate": "forecast/{timestamp}/{z}/{x}/{y}.png",
      "minZoom": 5,
      "maxZoom": 10,
      "runTime": "2026-05-13T21:00:00Z",
      "frames": [
        { "timestamp": "2026-05-13T21:00:00Z" },
        { "timestamp": "2026-05-13T21:15:00Z" },
        { "timestamp": "2026-05-13T21:30:00Z" }
      ]
    }
  }
}
"""

class TimelineTest {

    private fun decode(raw: String = MIXED_MANIFEST): Manifest =
        RadarHttpClient.json.decodeFromString(Manifest.serializer(), raw)

    @Test
    fun flattens_and_sorts_layers_chronologically() {
        val frames = decode().toTimeline("https://radar.example.tld")
        val timestamps = frames.map { it.timestamp.toString() }
        assertContentEquals(
            listOf(
                "2026-05-13T20:50:00Z",
                "2026-05-13T20:55:00Z",
                "2026-05-13T21:00:00Z",
                "2026-05-13T21:05:00Z",
                "2026-05-13T21:15:00Z",
                "2026-05-13T21:30:00Z",
            ),
            timestamps,
        )
    }

    @Test
    fun drops_nowcast_frames_overlapping_with_radar() {
        val frames = decode().toTimeline("https://radar.example.tld")
        // Nowcast at 20:55 clashes with the latest radar frame and is dropped.
        val nowcastTimes = frames.filter { it.kind == FrameKind.NOWCAST }.map { it.timestamp.toString() }
        assertContentEquals(
            listOf("2026-05-13T21:00:00Z", "2026-05-13T21:05:00Z"),
            nowcastTimes,
        )
    }

    @Test
    fun drops_forecast_frames_overlapping_with_radar_or_nowcast() {
        val frames = decode().toTimeline("https://radar.example.tld")
        // Forecast at 21:00 clashes with kept nowcast; only 21:15 and 21:30 survive.
        val forecastTimes = frames.filter { it.kind == FrameKind.FORECAST }.map { it.timestamp.toString() }
        assertContentEquals(
            listOf("2026-05-13T21:15:00Z", "2026-05-13T21:30:00Z"),
            forecastTimes,
        )
    }

    @Test
    fun tags_each_frame_with_its_layer_kind() {
        val kinds = decode().toTimeline("https://radar.example.tld").map { it.kind }
        assertEquals(
            listOf(
                FrameKind.RADAR, FrameKind.RADAR,
                FrameKind.NOWCAST, FrameKind.NOWCAST,
                FrameKind.FORECAST, FrameKind.FORECAST,
            ),
            kinds,
        )
    }

    @Test
    fun substitutes_timestamp_into_url_template_in_url_safe_form() {
        val frames = decode().toTimeline("https://radar.example.tld/")  // trailing slash trimmed
        val radar = frames.last { it.kind == FrameKind.RADAR }
        assertEquals(
            "https://radar.example.tld/radar/2026-05-13T20-55-00Z/{z}/{x}/{y}.png",
            radar.tileUrlTemplate,
        )
        assertTrue(radar.tileUrlTemplate.contains("{z}/{x}/{y}"))
        assertTrue(":50:" !in radar.tileUrlTemplate && ":55:" !in radar.tileUrlTemplate)
    }

    @Test
    fun carries_per_layer_zoom_bounds() {
        val frames = decode().toTimeline("https://radar.example.tld")
        frames.forEach {
            assertEquals(5, it.minZoom)
            assertEquals(10, it.maxZoom)
        }
    }
}
