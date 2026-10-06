import Combine
import Foundation

@MainActor
final class AppStore: ObservableObject {
    @Published private(set) var procurements: [Procurement]
    @Published private(set) var isLive = false
    @Published private(set) var isLoading = false
    @Published private(set) var lastError: String?

    private var apiClient: TenderAgentAPIClient?

    init(
        procurements: [Procurement] = MockData.procurements,
        apiClient: TenderAgentAPIClient? = TenderAgentAPIClient.preferred()
    ) {
        self.procurements = procurements
        self.apiClient = apiClient
    }

    var decisionNeeded: [Procurement] {
        procurements.filter { $0.decision == .pending || $0.decision == .deferred }
    }

    var submittedCount: Int {
        procurements.filter { $0.lifecycle == .submitted || $0.lifecycle == .outcome }.count
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
        if apiClient == nil { return "Mock data" }
        return "Ошибка backend"
    }

    func procurement(id: String) -> Procurement? {
        procurements.first { $0.id == id }
    }


    func configureConnection(
        baseURL: String,
        username: String,
        password: String
    ) async {
        do {
            let configuration = try BackendCredentialStore.save(
                baseURLString: baseURL,
                username: username,
                password: password
            )
            apiClient = TenderAgentAPIClient(configuration: configuration)
            await refresh()
        } catch {
            isLive = false
            lastError = error.localizedDescription
        }
    }

    func disconnect() {
        BackendCredentialStore.clear()
        apiClient = nil
        isLive = false
        lastError = nil
    }

    func refresh() async {
        guard let apiClient else {
            isLive = false
            return
        }
        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await apiClient.fetchPortfolio()
            procurements = response.items.map(Procurement.fromAPI)
            isLive = true
            lastError = nil
        } catch {
            isLive = false
            lastError = error.localizedDescription
        }
    }

    func setDecision(
        _ decision: HumanDecision,
        for id: String,
        comment: String? = nil,
        deferredUntil: Date? = nil
    ) {
        guard let index = procurements.firstIndex(where: { $0.id == id }) else { return }

        procurements[index].decision = decision
        procurements[index].decisionComment = comment
        procurements[index].deferredUntil = decision == .deferred ? deferredUntil : nil
    }

    func submitDecision(
        _ decision: HumanDecision,
        for id: String,
        comment: String? = nil,
        deferredUntil: Date? = nil
    ) async {
        guard let apiClient else {
            setDecision(decision, for: id, comment: comment, deferredUntil: deferredUntil)
            return
        }

        let action: String
        switch decision {
        case .go: action = "GO"
        case .noGo: action = "NO_GO"
        case .deferred: action = "DEFER"
        case .pending: return
        }

        do {
            let item = try await apiClient.recordDecision(
                dealID: id,
                action: action,
                rationale: comment,
                deferredUntil: deferredUntil
            )
            let updated = Procurement.fromAPI(item)
            if let index = procurements.firstIndex(where: { $0.id == id }) {
                procurements[index] = updated
            }
            isLive = true
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }
}
