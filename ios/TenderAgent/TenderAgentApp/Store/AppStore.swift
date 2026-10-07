import Combine
import Foundation

@MainActor
final class AppStore: ObservableObject {
    @Published private(set) var procurements: [Procurement]
    @Published private(set) var inboxSummary: MobileInboxSummary?
    @Published private(set) var portfolioSummary: MobilePortfolioSummary?
    @Published private(set) var isLive = false
    @Published private(set) var isLoading = false
    @Published private(set) var isMockData = true
    @Published private(set) var lastError: String?
    @Published private(set) var decisionInFlightID: String?
    @Published private(set) var decisionMessage: String?
    @Published private(set) var decisionError: String?
    @Published private(set) var lastDecisionDealID: String?
    @Published private(set) var pushStatusLabel = "Не запрошены"
    @Published private(set) var pushRegistrationError: String?

    private var apiClient: TenderAgentAPIClient?
    private var pendingAPNSToken: String?

    init(
        procurements: [Procurement] = MockData.procurements,
        apiClient: TenderAgentAPIClient? = TenderAgentAPIClient.preferred()
    ) {
        self.procurements = procurements
        self.apiClient = apiClient
        self.inboxSummary = nil
        self.portfolioSummary = nil
        self.isMockData = true
    }

    var decisionNeeded: [Procurement] {
        procurements.filter(\.needsAttention)
    }

    var totalPortfolioCount: Int {
        portfolioSummary?.totalConsidered ?? inboxSummary?.totalPortfolio ?? procurements.count
    }

    var submittedCount: Int {
        portfolioSummary?.submitted ?? procurements.filter(\.submitted).count
    }

    var goCount: Int {
        portfolioSummary?.go ?? procurements.filter { $0.portfolioDecision == .go }.count
    }

    var noGoCount: Int {
        portfolioSummary?.noGo ?? procurements.filter { $0.portfolioDecision == .noGo }.count
    }

    var wonCount: Int {
        portfolioSummary?.won ?? procurements.filter { $0.outcomeCode == "WON" }.count
    }

    var notWonCount: Int {
        if let portfolioSummary {
            return portfolioSummary.lost + portfolioSummary.rejected
        }
        return procurements.filter {
            $0.outcomeCode == "LOST" || $0.outcomeCode == "REJECTED"
        }.count
    }

    var cancelledCount: Int {
        portfolioSummary?.cancelled ?? procurements.filter { $0.outcomeCode == "CANCELLED" }.count
    }

    var submissionRate: Double {
        portfolioSummary?.submissionRate ?? (goCount == 0 ? 0 : Double(submittedCount) / Double(goCount))
    }

    var winRate: Double {
        if let portfolioSummary {
            return portfolioSummary.winRate
        }
        let decided = wonCount + notWonCount
        return decided == 0 ? 0 : Double(wonCount) / Double(decided)
    }

    func portfolioItems(for filter: PortfolioFilter) -> [Procurement] {
        procurements
            .filter(filter.matches)
            .sorted {
                if $0.updatedAt == $1.updatedAt {
                    return $0.registryNumber > $1.registryNumber
                }
                return $0.updatedAt > $1.updatedAt
            }
    }

    func portfolioCount(for filter: PortfolioFilter) -> Int {
        portfolioItems(for: filter).count
    }

    var canSubmitDecisions: Bool {
        apiClient != nil && !isMockData
    }

    var connectionLabel: String {
        if isLoading { return "Подключение…" }
        if isLive { return "Live backend" }
        if apiClient == nil { return "Не подключено" }
        return "Ошибка backend"
    }

    func isSubmittingDecision(for dealID: String) -> Bool {
        decisionInFlightID == dealID
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
            await syncPendingPushToken()
        } catch {
            isLive = false
            isMockData = true
            lastError = error.localizedDescription
        }
    }

    func disconnect() async {
        var revocationWarning: String?
        if let apiClient {
            do {
                try await apiClient.revokeDevice(deviceID: BackendCredentialStore.deviceID)
            } catch {
                revocationWarning =
                    "Локальное подключение сброшено, но push-регистрацию backend отозвать не удалось: \(error.localizedDescription)"
            }
        }

        BackendCredentialStore.clear()
        apiClient = nil
        procurements = MockData.procurements
        inboxSummary = nil
        portfolioSummary = nil
        isLive = false
        isMockData = true
        lastError = revocationWarning
        decisionInFlightID = nil
        decisionMessage = nil
        decisionError = nil
        lastDecisionDealID = nil
        pendingAPNSToken = nil
        pushStatusLabel = "Не подключено"
        pushRegistrationError = revocationWarning
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
            let portfolio = try await apiClient.fetchPortfolio()
            let inbox = try await apiClient.fetchInbox()
            procurements = portfolio.items.map(Procurement.fromAPI)
            portfolioSummary = portfolio.summary
            inboxSummary = inbox.summary
            isLive = true
            isMockData = false
            lastError = nil
        } catch {
            isLive = false
            lastError = error.localizedDescription
        }
    }

    func restorePushRegistrationIfAuthorized() async {
        let status = await PushNotificationRegistrar.registerIfAuthorized()
        pushStatusLabel = PushNotificationRegistrar.statusLabel(status)
    }

    func requestPushNotifications() async {
        pushRegistrationError = nil
        let status = await PushNotificationRegistrar.requestAuthorization()
        pushStatusLabel = PushNotificationRegistrar.statusLabel(status)
    }

    func receiveAPNSToken(_ token: String) async {
        let trimmed = token.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            handlePushRegistrationFailure("iOS вернула пустой APNs token.")
            return
        }
        pendingAPNSToken = trimmed
        pushStatusLabel = "APNs token получен — синхронизация"
        pushRegistrationError = nil
        await syncPendingPushToken()
    }

    func handlePushRegistrationFailure(_ message: String) {
        pushStatusLabel = "Ошибка APNs"
        pushRegistrationError = message
    }

    @discardableResult
    func refreshAndEnsureProcurementLoaded(id: String) async -> Bool {
        await refresh()
        if procurement(id: id) != nil {
            return true
        }
        return await ensureProcurementLoaded(id: id)
    }

    @discardableResult
    func ensureProcurementLoaded(id: String) async -> Bool {
        if procurement(id: id) != nil {
            return true
        }
        guard let apiClient, !isMockData else {
            lastError = "Не удалось открыть закупку из push: live backend не подключён."
            return false
        }
        do {
            let item = try await apiClient.fetchProcurement(dealID: id)
            upsert(Procurement.fromAPI(item))
            isLive = true
            lastError = nil
            return true
        } catch {
            lastError = "Не удалось открыть закупку из push: \(error.localizedDescription)"
            return false
        }
    }

    @discardableResult
    func submitDecision(
        dealID: String,
        action: MobileDecisionAction,
        rationale: String,
        deferredUntil: Date? = nil
    ) async -> Bool {
        lastDecisionDealID = dealID
        decisionMessage = nil
        decisionError = nil

        guard let apiClient, !isMockData else {
            decisionError = "Решения можно сохранять только в live backend. Подключите Tender Agent в настройках."
            return false
        }

        decisionInFlightID = dealID
        defer { decisionInFlightID = nil }

        let trimmedRationale = rationale.trimmingCharacters(in: .whitespacesAndNewlines)
        let effectiveDeferredUntil = action == .deferDecision ? deferredUntil : nil

        do {
            let response = try await apiClient.recordDecision(
                dealID: dealID,
                action: action,
                rationale: trimmedRationale.isEmpty ? nil : trimmedRationale,
                deferredUntil: effectiveDeferredUntil
            )
            upsert(Procurement.fromAPI(response))
            isLive = true
            isMockData = false
            decisionMessage = "\(action.displayTitle) сохранено в журнале решений."
            lastError = nil

            do {
                let portfolio = try await apiClient.fetchPortfolio()
                let inbox = try await apiClient.fetchInbox()
                procurements = portfolio.items.map(Procurement.fromAPI)
                portfolioSummary = portfolio.summary
                inboxSummary = inbox.summary
            } catch {
                lastError = "Решение сохранено, но портфель обновить не удалось: \(error.localizedDescription)"
            }
            return true
        } catch {
            decisionError = error.localizedDescription
            return false
        }
    }

    private func syncPendingPushToken() async {
        guard let pendingAPNSToken else {
            return
        }
        guard let apiClient, !isMockData else {
            pushStatusLabel = "APNs готов — подключите backend"
            return
        }

        do {
            let registration = try await apiClient.registerDevice(
                apnsToken: pendingAPNSToken,
                environment: .current,
                deviceName: BackendCredentialStore.deviceName,
                appVersion: Self.appVersion
            )
            pushStatusLabel = registration.enabled
                ? "Активны (\(registration.environment.rawValue))"
                : "Отключены backend"
            pushRegistrationError = nil
        } catch {
            pushStatusLabel = "Ошибка синхронизации push"
            pushRegistrationError = error.localizedDescription
        }
    }

    private func upsert(_ procurement: Procurement) {
        if let index = procurements.firstIndex(where: { $0.id == procurement.id }) {
            procurements[index] = procurement
        } else {
            procurements.append(procurement)
        }
    }

    private static var appVersion: String? {
        Bundle.main.object(
            forInfoDictionaryKey: "CFBundleShortVersionString"
        ) as? String
    }
}
