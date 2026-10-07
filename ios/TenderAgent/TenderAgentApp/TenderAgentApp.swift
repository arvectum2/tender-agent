import SwiftUI

@main
struct TenderAgentApp: App {
    @UIApplicationDelegateAdaptor(TenderAgentAppDelegate.self) private var appDelegate
    @StateObject private var store = AppStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(store)
                .task {
                    await store.bootstrap()
                    await store.restorePushRegistrationIfAuthorized()
                }
        }
    }
}
