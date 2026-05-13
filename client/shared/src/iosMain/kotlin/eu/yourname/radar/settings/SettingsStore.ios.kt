package eu.yourname.radar.settings

import platform.Foundation.NSUserDefaults

actual class SettingsStore {
    private val defaults = NSUserDefaults.standardUserDefaults

    actual fun getString(key: String, default: String?): String? =
        defaults.stringForKey(key) ?: default

    actual fun putString(key: String, value: String) {
        defaults.setObject(value, forKey = key)
    }

    actual fun remove(key: String) {
        defaults.removeObjectForKey(key)
    }
}
