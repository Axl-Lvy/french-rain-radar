# ADR 0003 — KMP with per-platform MapLibre via expect/actual

**Status:** Accepted
**Date:** 2026-05-13

## Context

The client targets Android, iOS, and the Web (WasmJS). The shared codebase needs a map view that renders an animated PNG ground overlay. There is no mature cross-platform Kotlin map library; the three viable map SDKs are MapLibre Android, MapLibre iOS, and maplibre-gl-js.

## Decision

- Use **Kotlin Multiplatform** + **Compose Multiplatform** for the entire UI shell, state management, and HTTP layer.
- The map view is a single `@Composable expect fun RadarMap(...)` declared in `commonMain`, with three `actual` implementations under `androidMain`, `iosMain`, and `wasmJsMain`, each wrapping the native MapLibre SDK for that platform.
- Reject the alternative of "MapLibre GL JS inside a WebView on all platforms" — it works but loses native gesture feel and is harder to debug.

## Consequences

**Positive**

- The ~95% of code that isn't the map view is shared.
- Each platform's map is implemented in the most natural way for that platform (Android `View`, UIKit view via cinterop, JS interop on Wasm).
- No vendor lock-in to a paid mapping SDK.

**Negative**

- Three platform-specific implementations to keep behaviourally aligned.
- iOS bindings require `cinterop` for MapLibre's Objective-C API (or a thin Swift wrapper).
- Wasm map integration uses Compose Web's HTML element escape hatch, which is the most fragile piece of the client.

## Alternatives considered

- **Flutter / React Native.** Outside the user's preferred stack (JVM/Kotlin fluency).
- **Mapbox/Google Maps.** Paid at scale and overkill for a free private radar app.
- **WebView with maplibre-gl-js on all three platforms.** Tempting but loses native feel; revisit if the Wasm map proves too painful.
