package eu.yourname.radar.map

import android.Manifest
import android.annotation.SuppressLint
import android.content.pm.PackageManager
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import eu.yourname.radar.data.Bbox
import eu.yourname.radar.domain.TimelineFrame
import okhttp3.OkHttpClient
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.location.LocationComponentActivationOptions
import org.maplibre.android.location.modes.CameraMode
import org.maplibre.android.location.modes.RenderMode
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.module.http.HttpRequestUtil
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.layers.RasterLayer
import org.maplibre.android.style.sources.RasterSource
import org.maplibre.android.style.sources.TileSet

// Positron: lightweight grayscale vector basemap from OpenFreeMap. Drawn fast
// (fewer style layers than Liberty) and lets the radar overlay stay readable.
private const val BASE_STYLE_URL = "https://tiles.openfreemap.org/styles/positron"
private const val MIN_ZOOM = 4.0
private const val MAX_ZOOM = 14.0

@Composable
actual fun RadarMap(
    bbox: Bbox,
    frames: List<TimelineFrame>,
    currentIndex: Int,
    tileAuthHeader: String,
    cameraTarget: Pair<Double, Double>?,
    userLocationEnabled: Boolean,
    modifier: Modifier,
) {
    val context = LocalContext.current
    val density = LocalDensity.current
    val lifecycleOwner = LocalLifecycleOwner.current

    DisposableEffect(tileAuthHeader) {
        val client = OkHttpClient.Builder()
            .addInterceptor { chain ->
                val original = chain.request()
                val path = original.url.encodedPath
                val toBackend = path.startsWith("/radar/")
                    || path.startsWith("/nowcast/")
                    || path.startsWith("/forecast/")
                val req = if (toBackend) {
                    original.newBuilder().header("Authorization", tileAuthHeader).build()
                } else original
                chain.proceed(req)
            }
            .build()
        HttpRequestUtil.setOkHttpClient(client)
        onDispose { HttpRequestUtil.setOkHttpClient(null) }
    }

    val mapView = remember {
        MapLibre.getInstance(context.applicationContext)
        MapView(context).apply { onCreate(null) }
    }
    var mapLibreMap: MapLibreMap? by remember { mutableStateOf(null) }
    val addedFrameIds = remember { mutableSetOf<String>() }

    DisposableEffect(lifecycleOwner, mapView) {
        when (lifecycleOwner.lifecycle.currentState) {
            Lifecycle.State.RESUMED -> { mapView.onStart(); mapView.onResume() }
            Lifecycle.State.STARTED -> { mapView.onStart() }
            else -> {}
        }
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> mapView.onStart()
                Lifecycle.Event.ON_RESUME -> mapView.onResume()
                Lifecycle.Event.ON_PAUSE -> mapView.onPause()
                Lifecycle.Event.ON_STOP -> mapView.onStop()
                Lifecycle.Event.ON_DESTROY -> mapView.onDestroy()
                else -> {}
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            mapView.onDestroy()
        }
    }

    AndroidView(
        modifier = modifier,
        factory = {
            mapView.getMapAsync { map ->
                map.setStyle(Style.Builder().fromUri(BASE_STYLE_URL)) {
                    val bounds = LatLngBounds.from(
                        bbox.latMax, bbox.lonMax, bbox.latMin, bbox.lonMin,
                    )
                    map.setLatLngBoundsForCameraTarget(bounds)
                    map.setMinZoomPreference(MIN_ZOOM)
                    map.setMaxZoomPreference(MAX_ZOOM)
                    map.moveCamera(CameraUpdateFactory.newLatLngBounds(bounds, 16))

                    map.uiSettings.apply {
                        isCompassEnabled = true
                        val topMarginPx = with(density) { 64.dp.toPx().toInt() }
                        val sideMarginPx = with(density) { 12.dp.toPx().toInt() }
                        setCompassMargins(0, topMarginPx, sideMarginPx, 0)
                    }
                    mapLibreMap = map
                }
            }
            mapView
        },
    )

    LaunchedEffect(frames, mapLibreMap) {
        val map = mapLibreMap ?: return@LaunchedEffect
        val style = map.style ?: return@LaunchedEffect
        if (!style.isFullyLoaded) return@LaunchedEffect

        val wanted = frames.mapTo(mutableSetOf()) { it.layerId }
        addedFrameIds.filter { it !in wanted }.forEach { stale ->
            style.getLayer(stale)?.let { style.removeLayer(it) }
            style.getSource(stale)?.let { style.removeSource(it) }
            addedFrameIds.remove(stale)
        }
        frames.forEach { frame ->
            if (frame.layerId in addedFrameIds) return@forEach
            val tileSet = TileSet("2.2.0", frame.tileUrlTemplate).apply {
                minZoom = frame.minZoom.toFloat()
                maxZoom = frame.maxZoom.toFloat()
            }
            style.addSource(RasterSource(frame.layerId, tileSet, 256))
            style.addLayer(
                RasterLayer(frame.layerId, frame.layerId).withProperties(
                    PropertyFactory.rasterOpacity(0f),
                ),
            )
            addedFrameIds.add(frame.layerId)
        }
    }

    LaunchedEffect(currentIndex, frames, mapLibreMap) {
        val map = mapLibreMap ?: return@LaunchedEffect
        val style = map.style ?: return@LaunchedEffect
        if (!style.isFullyLoaded) return@LaunchedEffect

        val activeId = frames.getOrNull(currentIndex)?.layerId
        addedFrameIds.forEach { id ->
            val layer = style.getLayer(id) as? RasterLayer ?: return@forEach
            val opacity = if (id == activeId) 0.75f else 0f
            layer.setProperties(PropertyFactory.rasterOpacity(opacity))
        }
    }

    LaunchedEffect(cameraTarget, mapLibreMap) {
        val (lat, lon) = cameraTarget ?: return@LaunchedEffect
        val map = mapLibreMap ?: return@LaunchedEffect
        map.animateCamera(
            CameraUpdateFactory.newLatLngZoom(LatLng(lat, lon), 11.0),
        )
    }

    // Blue-dot user-position renderer. Activated lazily once the user has
    // granted location permission (signalled by [userLocationEnabled]).
    LaunchedEffect(userLocationEnabled, mapLibreMap) {
        if (!userLocationEnabled) return@LaunchedEffect
        val map = mapLibreMap ?: return@LaunchedEffect
        val style = map.style ?: return@LaunchedEffect
        if (!style.isFullyLoaded) return@LaunchedEffect
        if (ContextCompat.checkSelfPermission(
                context, Manifest.permission.ACCESS_FINE_LOCATION,
            ) != PackageManager.PERMISSION_GRANTED
        ) return@LaunchedEffect

        @SuppressLint("MissingPermission")
        run {
            val lc = map.locationComponent
            if (!lc.isLocationComponentActivated) {
                lc.activateLocationComponent(
                    LocationComponentActivationOptions.builder(context, style)
                        .useDefaultLocationEngine(true)
                        .build(),
                )
            }
            lc.isLocationComponentEnabled = true
            lc.cameraMode = CameraMode.NONE
            lc.renderMode = RenderMode.NORMAL
        }
    }
}
