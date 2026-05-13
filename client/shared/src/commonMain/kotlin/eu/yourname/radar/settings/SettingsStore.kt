package eu.yourname.radar.settings

/**
 * Tiny persistent key/value store backed by the platform default
 * (SharedPreferences / NSUserDefaults / localStorage).
 */
expect class SettingsStore() {
    fun getString(key: String, default: String? = null): String?
    fun putString(key: String, value: String)
    fun remove(key: String)
}

object SettingsKeys {
    const val USERNAME = "auth.username"
    const val PASSWORD = "auth.password"
    const val BASE_URL = "backend.baseUrl"
}
