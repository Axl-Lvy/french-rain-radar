# iosApp/

This directory is the Xcode side of the iOS build. The Kotlin `:shared` module
produces an XCFramework consumed here.

**You need macOS + Xcode 16+ to build iOS.**

## First-time setup on a Mac

1. Open `iosApp.xcodeproj` (you'll need to create it the first time — see below).
2. Add the `:shared` framework via SPM or CocoaPods.

## Creating the Xcode project (one-time, on a Mac)

This scaffold ships only the Swift entry-point files; the `.xcodeproj` is not
checked in because hand-rolled `project.pbxproj` files are fragile. To create it:

```bash
cd client/iosApp
# Generate a minimal Xcode project. Two reasonable paths:
#   1) Use the IntelliJ/Fleet "New KMP iOS App" wizard.
#   2) Use XcodeGen with the project.yml below:
xcodegen
```

A minimal `project.yml` (XcodeGen) you can drop in:

```yaml
name: iosApp
options:
  bundleIdPrefix: eu.yourname.radar
targets:
  iosApp:
    type: application
    platform: iOS
    sources: [iosApp]
    info:
      path: iosApp/Info.plist
      properties:
        UILaunchStoryboardName: ""
    settings:
      base:
        TARGETED_DEVICE_FAMILY: "1,2"
        IPHONEOS_DEPLOYMENT_TARGET: "15.0"
        SWIFT_VERSION: "5"
```

Then from the project root run:

```bash
cd client
./gradlew :shared:linkPodReleaseFrameworkIosArm64
```

and add the produced `shared.framework` to the Xcode target's "Frameworks, Libraries, and Embedded Content".

## Source files

- `iosApp/iOSApp.swift` — `@main` entry, hosts a `ComposeUIViewController`.
- `iosApp/ContentView.swift` — SwiftUI wrapper for the Compose root.
- `iosApp/Info.plist` — bundle metadata.
