import SwiftUI

private enum RootTab: Hashable {
    case inbox
    case portfolio
    case settings
}

struct RootView: View {
    @EnvironmentObject private var store: AppStore

    @State private var selectedTab: RootTab = .inbox
    @State private var inboxPath: [String] = []
    @State private var portfolioPath: [String] = []

    var body: some View {
        TabView(selection: $selectedTab) {
            Tab("Входящие", systemImage: "tray.full", value: RootTab.inbox) {
                NavigationStack(path: $inboxPath) {
                    InboxView()
                        .navigationDestination(for: String.self) { id in
                            ProcurementDetailView(procurementID: id)
                        }
                }
            }

            Tab("Портфель", systemImage: "briefcase", value: RootTab.portfolio) {
                NavigationStack(path: $portfolioPath) {
                    PortfolioView()
                        .navigationDestination(for: String.self) { id in
                            ProcurementDetailView(procurementID: id)
                        }
                }
            }

            Tab("Настройки", systemImage: "gearshape", value: RootTab.settings) {
                NavigationStack {
                    SettingsView()
                }
            }
        }
        .onOpenURL { url in
            guard let deepLink = TenderAgentDeepLink(url: url) else {
                return
            }
            route(deepLink)
        }
        .onReceive(
            NotificationCenter.default.publisher(for: .tenderAgentDeepLink)
        ) { notification in
            guard
                let url = notification.object as? URL,
                let deepLink = TenderAgentDeepLink(url: url)
            else {
                return
            }
            route(deepLink)
        }
        .onReceive(
            NotificationCenter.default.publisher(for: .tenderAgentAPNSToken)
        ) { notification in
            guard let token = notification.object as? String else {
                return
            }
            Task {
                await store.receiveAPNSToken(token)
            }
        }
        .onReceive(
            NotificationCenter.default.publisher(
                for: .tenderAgentPushRegistrationFailure
            )
        ) { notification in
            guard let message = notification.object as? String else {
                return
            }
            store.handlePushRegistrationFailure(message)
        }
    }

    private func route(_ deepLink: TenderAgentDeepLink) {
        switch deepLink {
        case .digest:
            selectedTab = .inbox
            inboxPath.removeAll()
        case let .procurement(dealID):
            selectedTab = .inbox
            Task {
                if await store.ensureProcurementLoaded(id: dealID) {
                    inboxPath = [dealID]
                }
            }
        }
    }
}
