package eu.yourname.radar.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Place
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat

@Composable
actual fun LocationFab(
    onLocate: (lat: Double, lon: Double) -> Unit,
    modifier: Modifier,
) {
    val context = LocalContext.current
    var pendingFix by remember { mutableStateOf(false) }

    val permLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) pendingFix = true
    }

    LaunchedEffect(pendingFix) {
        if (!pendingFix) return@LaunchedEffect
        pendingFix = false
        getMostRecentLocation(context)?.let { onLocate(it.latitude, it.longitude) }
    }

    FloatingActionButton(
        onClick = {
            val granted = ContextCompat.checkSelfPermission(
                context, Manifest.permission.ACCESS_FINE_LOCATION,
            ) == PackageManager.PERMISSION_GRANTED
            if (granted) {
                getMostRecentLocation(context)?.let { onLocate(it.latitude, it.longitude) }
            } else {
                permLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
            }
        },
        modifier = modifier,
    ) { Icon(Icons.Filled.Place, contentDescription = "Centre on my location") }
}

private fun getMostRecentLocation(context: Context): Location? {
    val lm = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return null
    return lm.getProviders(/* enabledOnly = */ true)
        .mapNotNull {
            try {
                lm.getLastKnownLocation(it)
            } catch (_: SecurityException) {
                null
            }
        }
        .maxByOrNull { it.time }
}
