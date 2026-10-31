import SwiftUI

@main
struct TapApp: App {
    @StateObject private var model = BlockModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(model)
        }
    }
}
