import SwiftUI

struct RootView: View {
    var body: some View {
        TabView {
            Tab("Входящие", systemImage: "tray.full") {
                NavigationStack {
                    InboxView()
                }
            }

            Tab("Настройки", systemImage: "gearshape") {
                NavigationStack {
                    SettingsView()
                }
            }
        }
    }
}
