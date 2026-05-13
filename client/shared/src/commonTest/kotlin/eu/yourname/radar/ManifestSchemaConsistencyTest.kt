package eu.yourname.radar

import eu.yourname.radar.data.Manifest
import eu.yourname.radar.data.RadarHttpClient
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Decodes the example manifest into the Kotlin model. Compiled into the source
 * tree so it works on all KMP targets without filesystem access.
 *
 * Keep this string in sync with `schema/examples/manifest.example.json`. CI
 * verifies by diffing the file against this literal (see .github/workflows/client.yml).
 */
private const val EXAMPLE_MANIFEST = """
{
  "manifestVersion": 1,
  "generatedAt": "2026-05-13T14:30:00Z",
  "bbox": { "latMin": 43.6, "latMax": 44.2, "lonMin": 4.6, "lonMax": 5.6 },
  "tileSize": { "width": 512, "height": 384 },
  "colorScale": "rainviewer-original",
  "layers": {
    "radar":    { "frames": [{ "timestamp": "2026-05-13T14:25:00Z", "url": "radar/2026-05-13T14-25-00.png" }] },
    "nowcast":  { "frames": [{ "timestamp": "2026-05-13T14:30:00Z", "url": "nowcast/2026-05-13T14-30-00.png" }] },
    "forecast": { "frames": [{ "timestamp": "2026-05-13T15:30:00Z", "url": "forecast/2026-05-13T15-30-00.png" }] }
  }
}
"""

class ManifestSchemaConsistencyTest {
    @Test
    fun example_manifest_decodes() {
        val m = RadarHttpClient.json.decodeFromString(Manifest.serializer(), EXAMPLE_MANIFEST)
        assertEquals(1, m.manifestVersion)
        assertEquals(43.6, m.bbox.latMin)
        assertEquals(512, m.tileSize.width)
        assertEquals(1, m.layers.radar?.frames?.size)
    }
}
