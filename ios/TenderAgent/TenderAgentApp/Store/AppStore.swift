import Combine
import Foundation

@MainActor
final class AppStore: ObservableObject {
    @Published private(set) var procurements: [Procurement]
    @Published private(set) var inboxSummary: MobileInboxSummary?
    @Published private(set) var isLive = false
    @Published private(set) var isLoading = false
    @Published private(set) var isMockData = true
    @Published private(set) var lastError: String?

    private var apiClient: TenderAgentAPIClient?

    init(
        procurements: [Procurement] = MockData.procurements,
        apiClient: TenderAgentAPIClient? = TenderAgentAPIClient.preferred()
    ) {
        self.procurements = procurements
        self.apiClient = apiClient
        self.inboxSummary = nil
        self.isMockData = true
    }

    var decisionNeeded: [Procurement] {
        procurements.filter(\.needsAttention)
    }

    var totalPortfolioCount: Int {
        inboxSummary?.totalPortfolio ?? procurements.count
    }

    var submittedCount: Int {
        inboxSummary?.submitted
            ?? procurements.filter { $0.lifecycle == .submitted || $0.lifecycle == .outcome }.count
    }

    var goCount: Int {
        procurements.filter { $0.decision == .go }.count
    }

    var noGoCount: Int {
        procurements.filter { $0.decision == .noGo }.count
    }

    var connectionLabel: String {
        if isLoading { return "Подключение…" }
        if isLive { return "Live backend" }
        if apiClient == nil { return "Не подключено" }
        return "Ошибка backend"
    }

    func bootstrap() async {
        let environment = ProcessInfo.processInfo.environment

        if apiClient == nil,
           let code = environment["TENDER_AGENT_PAIRING_CODE"],
           !code.isEmpty {
            let baseURL =
                environment["TENDER_AGENT_API_BASE_URL"]
                ?? BackendCredentialStore.defaultBaseURLString
            await pair(baseURL: baseURL, pairingCode: code)
            return
        }

        await refresh()
    }

    func procurement(id: String) -> Procurement? {
        procurements.first { $0.id == id }
    }

    func pair(
        baseURL: String,
        pairingCode: String
    ) async {
        isLoading = true
        defer { isLoading = false }

        do {
            guard let url = URL(
                string: baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
            ) else {
                throw CredentialStoreError.invalidURL
            }

            let pairingClient = TenderAgentPairingClient(baseURL: url)
            let response = try await pairingClient.pair(
                code: pairingCode.trimmingCharacters(in: .whitespacesAndNewlines),
                deviceID: BackendCredentialStore.deviceID,
                deviceName: BackendCredentialStore.deviceName
            )
            let configuration = try BackendCredentialStore.savePairing(
                baseURLString: baseURL,
                accessToken: response.accessToken
            )
            apiClient = TenderAgentAPIClient(configuration: configuration)
            lastError = nil
            await refresh()
        } catch {
            isLive = false
            isMockData = true
            lastError = error.localizedDescription
        }
    }

    func disconnect() {
        BackendCredentialStore.clear()
        apiClient = nil
        procurements = MockData.procurements
        inboxSummary = nil
        isLive = false
        isMockData = true
        lastError = nil
    }

    func refresh() async {
        guard let apiClient else {
            isLive = false
            isMockData = true
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await apiClient.fetchInbox()
            procurements = response.items.map(Procurement.fromAPI)
            inboxSummary = response.summary
            isLive = true
            isMockData = false
            lastError = nil
        } catch {
            isLive = false
            lastError = error.localizedDescription
        }
    }
}
