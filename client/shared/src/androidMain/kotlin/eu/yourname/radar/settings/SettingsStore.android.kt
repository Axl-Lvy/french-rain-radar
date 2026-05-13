package eu.yourname.radar.settings

import android.content.Context
import android.content.SharedPreferences

/**
 * Android backing. The default constructor is unhelpful here because we need a
 * Context; in real wiring the SettingsStore should be provided via DI (Koin)
 * with the application context bound at startup.
 *
 * Phase 0 keeps this as a no-op so the module compiles; replace with a
 * `Context`-aware variant in Phase 1.
 */
actual class SettingsStore {
    private var prefs: SharedPreferences? = null
    fun bind(context: Context) {
        prefs = context.getSharedPreferences("radar.prefs", Context.MODE_PRIVATE)
    }

    actual fun getString(key: String, default: String?): String? =
        prefs?.getString(key, default) ?: default

    actual fun putString(key: String, value: String) {
        prefs?.edit()?.putString(key, value)?.apply()
    }

    actual fun remove(key: String) {
        prefs?.edit()?.remove(key)?.apply()
    }
}
