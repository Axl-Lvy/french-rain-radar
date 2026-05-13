package eu.yourname.radar

import eu.yourname.radar.data.Manifest
import eu.yourname.radar.data.RadarHttpClient
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull

/**
 * Decodes the example manifest into the Kotlin model. Compiled into the source
 * tree so it works on all KMP targets without filesystem access.
 *
 * Keep this string in sync with `schema/examples/manifest.example.json`. CI
 * verifies by diffing the file against this literal (see .github/workflows/client.yml).
 */
private const val EXAMPLE_MANIFEST = """
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
    "forecast": {
      "tileUrlTemplate": "forecast/{timestamp}/{z}/{x}/{y}.png",
      "minZoom": 5,
      "maxZoom": 10,
      "runTime": "2026-05-13T20:00:00Z",
      "frames": [
        { "timestamp": "2026-05-13T20:15:00Z" },
        { "timestamp": "2026-05-13T20:30:00Z" },
        { "timestamp": "2026-05-13T20:45:00Z" }
      ]
    }
  }
}
"""

class ManifestSchemaConsistencyTest {
    @Test
    fun example_manifest_decodes() {
        val m = RadarHttpClient.json.decodeFromString(Manifest.serializer(), EXAMPLE_MANIFEST)
        assertEquals(2, m.manifestVersion)
        assertEquals(41.3, m.bbox.latMin)
        val radar = m.layers.radar
        assertNotNull(radar)
        assertEquals("radar/{timestamp}/{z}/{x}/{y}.png", radar.tileUrlTemplate)
        assertEquals(5, radar.minZoom)
        assertEquals(10, radar.maxZoom)
        assertEquals(2, radar.frames.size)
        assertNotNull(m.layers.forecast?.runTime)
    }
}
