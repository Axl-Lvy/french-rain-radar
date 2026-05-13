import SwiftUI
import UIKit
// import shared  // produced by `./gradlew :shared:linkPodReleaseFrameworkIosArm64`

/// Hosts the Compose Multiplatform root inside SwiftUI.
struct ContentView: View {
    var body: some View {
        ComposeView()
            .ignoresSafeArea(.keyboard)
    }
}

struct ComposeView: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> UIViewController {
        // TODO: return MainViewControllerKt.MainViewController() once a
        // commonMain `fun MainViewController(): UIViewController` is exported
        // from :shared.
        return UIViewController()
    }
    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}
}
