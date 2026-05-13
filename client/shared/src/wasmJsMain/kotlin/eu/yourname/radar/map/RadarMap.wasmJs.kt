package eu.yourname.radar.map

import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import eu.yourname.radar.data.Bbox
import eu.yourname.radar.domain.TimelineFrame

/**
 * Wasm actual mounts maplibre-gl-js into the `<div id="map">` declared in
 * `index.html`. The map element lives *outside* the Compose canvas (above it
 * in the DOM, in a separate fixed-position region), so we can't host it
 * inside the Compose tree — instead the composable runs `DisposableEffect`
 * to manage the JS map's lifecycle, and returns no UI.
 *
 * One [maplibregl.Map] source + raster layer is added per timeline frame,
 * with `raster-opacity: 0` for inactive ones. Scrubbing only flips opacity,
 * so MapLibre never re-fetches tiles (and the basemap + tile cache stays
 * warm). The auth header is injected via `transformRequest`.
 */
@Composable
actual fun RadarMap(
    bbox: Bbox,
    frames: List<TimelineFrame>,
    currentIndex: Int,
    tileAuthHeader: String,
    cameraTarget: Pair<Double, Double>?,
    userLocationEnabled: Boolean,  // Web uses maplibregl.GeolocateControl natively; param is unused here.
    modifier: Modifier,
) {
    val mapKey = remember(bbox.latMin, bbox.latMax, bbox.lonMin, bbox.lonMax, tileAuthHeader) { Any() }

    DisposableEffect(mapKey) {
        val map = jsCreateMap(
            containerId = "map",
            latMin = bbox.latMin,
            latMax = bbox.latMax,
            lonMin = bbox.lonMin,
            lonMax = bbox.lonMax,
            authHeader = tileAuthHeader,
        )
        onDispose { jsRemoveMap(map) }
    }

    // Encode the timeline as a JSON string and let JS update the source set.
    val framesJson = remember(frames) { encodeFramesJson(frames) }
    LaunchedEffect(framesJson) {
        jsSyncFrames(framesJson)
    }

    LaunchedEffect(currentIndex, frames) {
        val active = frames.getOrNull(currentIndex)?.layerId.orEmpty()
        jsSetActiveLayer(active)
    }

    LaunchedEffect(cameraTarget) {
        val (lat, lon) = cameraTarget ?: return@LaunchedEffect
        jsFlyTo(lat, lon)
    }

    Box(modifier = modifier)
}

private fun encodeFramesJson(frames: List<TimelineFrame>): String = buildString {
    append("[")
    frames.forEachIndexed { i, f ->
        if (i > 0) append(",")
        append("""{"id":"""")
        append(f.layerId)
        append("""","url":"""")
        append(f.tileUrlTemplate.replace("\\", "\\\\").replace("\"", "\\\""))
        append("""","minZoom":""")
        append(f.minZoom)
        append(""","maxZoom":""")
        append(f.maxZoom)
        append("}")
    }
    append("]")
}

private external interface MapHandle

@JsFun(
    """
    (containerId, latMin, latMax, lonMin, lonMax, authHeader) => {
      const bounds = [[lonMin, latMin], [lonMax, latMax]];
      const map = new maplibregl.Map({
        container: containerId,
        style: 'https://tiles.openfreemap.org/styles/positron',
        bounds: bounds,
        fitBoundsOptions: { padding: 16, animate: false },
        maxBounds: bounds,
        minZoom: 4,
        maxZoom: 14,
        attributionControl: { compact: true },
        transformRequest: (url, resourceType) => {
          if (resourceType === 'Tile' && (
                url.includes('/radar/') ||
                url.includes('/nowcast/') ||
                url.includes('/forecast/'))) {
            return { url: url, headers: { 'Authorization': authHeader } };
          }
          return { url: url };
        }
      });
      // NavigationControl has zoom +/- and a compass; clicking the compass
      // resets bearing to 0 (north up).
      map.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: false }), 'top-right');
      map.addControl(new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: false,
        showUserLocation: true,
      }), 'top-right');
      window.__radarMap = map;
      window.__radarFrames = new Set();
      return map;
    }
    """,
)
private external fun jsCreateMap(
    containerId: String,
    latMin: Double,
    latMax: Double,
    lonMin: Double,
    lonMax: Double,
    authHeader: String,
): MapHandle

@JsFun(
    """
    (framesJson) => {
      const map = window.__radarMap;
      if (!map) return;
      const frames = JSON.parse(framesJson);
      const apply = () => {
        const wanted = new Set(frames.map(f => f.id));
        // Drop layers/sources that aren't in the new timeline.
        for (const id of Array.from(window.__radarFrames)) {
          if (!wanted.has(id)) {
            if (map.getLayer(id)) map.removeLayer(id);
            if (map.getSource(id)) map.removeSource(id);
            window.__radarFrames.delete(id);
          }
        }
        // Add new ones with opacity 0 — MapLibre preloads tiles for visible
        // layers regardless of opacity, so all frames warm in parallel.
        for (const f of frames) {
          if (window.__radarFrames.has(f.id)) continue;
          map.addSource(f.id, {
            type: 'raster', tiles: [f.url], tileSize: 256,
            minzoom: f.minZoom, maxzoom: f.maxZoom,
          });
          map.addLayer({
            id: f.id, type: 'raster', source: f.id,
            paint: { 'raster-opacity': 0, 'raster-opacity-transition': { duration: 0 } },
          });
          window.__radarFrames.add(f.id);
        }
      };
      if (map.isStyleLoaded()) { apply(); } else { map.once('load', apply); }
    }
    """,
)
private external fun jsSyncFrames(framesJson: String)

@JsFun(
    """
    (activeId) => {
      const map = window.__radarMap;
      if (!map) return;
      const apply = () => {
        for (const id of window.__radarFrames) {
          map.setPaintProperty(id, 'raster-opacity', id === activeId ? 0.75 : 0);
        }
      };
      if (map.isStyleLoaded()) { apply(); } else { map.once('load', apply); }
    }
    """,
)
private external fun jsSetActiveLayer(activeId: String)

@JsFun(
    """
    (lat, lon) => {
      const map = window.__radarMap;
      if (!map) return;
      map.flyTo({ center: [lon, lat], zoom: 11, speed: 1.4 });
    }
    """,
)
private external fun jsFlyTo(lat: Double, lon: Double)

@JsFun(
    """
    (map) => {
      if (window.__radarMap === map) {
        window.__radarMap = null;
        window.__radarFrames = new Set();
      }
      map.remove();
    }
    """,
)
private external fun jsRemoveMap(map: MapHandle)
