# client/

Kotlin Multiplatform app, Compose Multiplatform UI, targeting **Android**, **iOS**, and **WasmJS**.

## Requirements

- JDK 21
- Android SDK (for the Android target)
- Xcode + a macOS machine (for the iOS target only)
- A modern browser (for the Wasm target)

## Build commands

```bash
# Run shared tests on the JVM
./gradlew :shared:allTests

# Android debug APK
./gradlew :androidApp:assembleDebug

# Wasm dev server (opens at http://localhost:8080/)
./gradlew :wasmJsApp:wasmJsBrowserDevelopmentRun

# Wasm production bundle
./gradlew :wasmJsApp:wasmJsBrowserDistribution

# iOS framework (cross-compilable from Linux; consuming it needs a Mac)
./gradlew :shared:linkPodReleaseFrameworkIosArm64
```

## Source layout

```
shared/                            shared module
  src/commonMain/                  Compose UI, viewmodels, repos, models
  src/androidMain/                 MapLibre Android actual + Android storage
  src/iosMain/                     MapLibre iOS actual + NSUserDefaults storage
  src/wasmJsMain/                  maplibre-gl-js actual + localStorage storage

androidApp/                        Android entry point (single Activity)
iosApp/                            Xcode project consuming :shared framework
wasmJsApp/                         Browser entry point
```

The map view is declared as `expect @Composable fun RadarMap(...)` in `commonMain` and implemented per platform.

## Configuration for local dev against the dev backend

The shared `HttpClient` reads its base URL from the build-time placeholder `RADAR_BASE_URL` (default `http://10.0.2.2:8080` on Android emulator, `http://localhost:8080` on Wasm/iOS simulator). Username / password defaults are `dev` / `dev` matching `backend/caddy/Caddyfile.dev`.
