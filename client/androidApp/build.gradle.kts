import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.compose.multiplatform)
    alias(libs.plugins.compose.compiler)
}

kotlin {
    androidTarget {
        compilerOptions { jvmTarget.set(JvmTarget.JVM_21) }
    }
    sourceSets {
        androidMain.dependencies {
            implementation(project(":shared"))
            implementation(libs.androidx.activity.compose)
            implementation(compose.runtime)
            implementation(compose.foundation)
            implementation(compose.material3)
        }
    }
}

// Release signing config is read from gitignored local.properties (or env vars),
// so the keystore + passwords stay out of the repo. Required keys:
//   radar.keystore.path     — absolute path to the .keystore file
//   radar.keystore.password — store password
//   radar.key.alias         — key alias
//   radar.key.password      — key password
// Falls back to env vars RADAR_KEYSTORE_PATH / RADAR_KEYSTORE_PASSWORD /
// RADAR_KEY_ALIAS / RADAR_KEY_PASSWORD when local.properties is missing
// (CI machines).
val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
fun cfg(key: String, env: String): String? =
    localProps.getProperty(key) ?: System.getenv(env)

android {
    namespace = "eu.yourname.radar"
    compileSdk = libs.versions.android.compile.sdk.get().toInt()
    defaultConfig {
        applicationId = "eu.yourname.radar"
        minSdk = libs.versions.android.min.sdk.get().toInt()
        targetSdk = libs.versions.android.target.sdk.get().toInt()
        versionCode = 2
        versionName = "0.2.0"
    }
    signingConfigs {
        create("release") {
            val storePath = cfg("radar.keystore.path", "RADAR_KEYSTORE_PATH")
            if (!storePath.isNullOrBlank()) {
                storeFile = file(storePath)
                storePassword = cfg("radar.keystore.password", "RADAR_KEYSTORE_PASSWORD")
                keyAlias = cfg("radar.key.alias", "RADAR_KEY_ALIAS") ?: "radar"
                keyPassword = cfg("radar.key.password", "RADAR_KEY_PASSWORD")
            }
        }
    }
    buildTypes {
        release {
            // Compose + MapLibre would need a non-trivial proguard ruleset to
            // survive R8; for a personal-scale release the size win isn't
            // worth the maintenance burden. The APK is ~55 MB either way.
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }
    // KMP source-set layout v2: everything lives under src/androidMain/
    // (kotlin/, AndroidManifest.xml, res/). The kotlin.mpp.androidSourceSetLayoutVersion=2
    // property in gradle.properties opts in.
}
