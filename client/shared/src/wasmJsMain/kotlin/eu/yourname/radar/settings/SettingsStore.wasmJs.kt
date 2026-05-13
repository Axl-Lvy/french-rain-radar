package eu.yourname.radar.settings

import kotlinx.browser.localStorage
import org.w3c.dom.get
import org.w3c.dom.set

actual class SettingsStore {
    actual fun getString(key: String, default: String?): String? =
        localStorage[key] ?: default

    actual fun putString(key: String, value: String) {
        localStorage[key] = value
    }

    actual fun remove(key: String) {
        localStorage.removeItem(key)
    }
}
