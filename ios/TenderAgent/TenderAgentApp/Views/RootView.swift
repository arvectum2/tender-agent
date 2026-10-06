import SwiftUI

struct RootView: View {
    var body: some View {
        TabView {
            Tab("Входящие", systemImage: "tray.full") {
                NavigationStack {
                    InboxView()
                }
            }

            Tab("Портфель", systemImage: "briefcase") {
                NavigationStack {
                    PortfolioView()
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
