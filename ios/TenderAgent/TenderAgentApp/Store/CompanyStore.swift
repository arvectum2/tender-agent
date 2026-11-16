import Combine
import Foundation

@MainActor
final class CompanyStore: ObservableObject {
    @Published private(set) var connections: [CompanyConnection] = []
    @Published private(set) var selectedID: String?
    @Published private(set) var identity: CompanyIdentity?
    @Published private(set) var items: [CompanyCase] = []
    @Published private(set) var hasMore = false
    @Published private(set) var isBusy = false
    @Published private(set) var error: String?
    @Published private(set) var loaded = false
    @Published private(set) var storageReady = false
    @Published private(set) var decisionNotice: String?
    @Published private(set) var inboxFilter: CompanyInboxFilter = .attention
    @Published private(set) var inboxSummary: CompanyInboxSummary?
    @Published private(set) var inboxAsOf: Date?
    private var nextOffset = 0
    private var pendingDecision: CompanyDecisionAttempt?
    private var pendingLifecycle: CompanyLifecycleAttempt?
    @Published private(set) var lifecycleMetrics: CompanyLifecycleMetrics?
    @Published private(set) var lifecycleNotice: String?

    init() {
        do {
            connections = try CompanyCredentialStore.load()
            storageReady = true
        } catch { self.error = CompanyConnectionError.storage.localizedDescription }
    }

    private var selected: CompanyConnection? { connections.first { $0.id == selectedID } }

    private func resetSelection(_ id: String? = nil) {
        if selectedID != id { pendingDecision = nil; pendingLifecycle = nil; inboxFilter = .attention }
        selectedID = id
        decisionNotice = nil
        lifecycleMetrics = nil; lifecycleNotice = nil
        identity = nil
        items = []
        inboxSummary = nil; inboxAsOf = nil; nextOffset = 0
        hasMore = false
        loaded = false
        error = nil
    }

    func connect(origin: String, token: String) async -> Bool {
        guard storageReady, !isBusy else { return false }
        isBusy = true
        defer { isBusy = false }
        resetSelection()
        do {
            let client = try CompanyAPIClient(origin: origin, token: token)
            let actual = try await client.identity()
            let account = CompanyConnection(baseURL: client.baseURL, token: token, identity: actual)
            var updated = connections.filter { $0.id != account.id }
            updated.append(account)
            try CompanyCredentialStore.save(updated)
            connections = updated
            resetSelection(account.id)
            await load(account, offset: 0)
            return true
        } catch { self.error = Self.safeError(error); return false }
    }

    func select(_ id: String) async {
        guard !isBusy, let account = connections.first(where: { $0.id == id }) else { return }
        isBusy = true
        defer { isBusy = false }
        resetSelection(id)
        await load(account, offset: 0)
    }

    func refresh() async {
        guard let account = selected else { return }
        await select(account.id)
    }

    func nextPage() async {
        guard !isBusy, loaded, hasMore, let account = selected else { return }
        isBusy = true
        defer { isBusy = false }
        await load(account, offset: nextOffset)
    }

    func setInboxFilter(_ filter: CompanyInboxFilter) async {
        guard !isBusy, let account = selected else { return }
        isBusy = true
        defer { isBusy = false }
        resetSelection(account.id)
        inboxFilter = filter
        await load(account, offset: 0)
    }

    private func load(_ account: CompanyConnection, offset: Int) async {
        do {
            let client = try CompanyAPIClient(connection: account)
            let actual = try await client.verifiedIdentity(for: account.identity)
            guard actual.legalAccepted else {
                lifecycleMetrics = nil; lifecycleNotice = nil
                identity = actual
                items = []
                inboxSummary = nil; inboxAsOf = nil; nextOffset = 0
                hasMore = false
                loaded = false
                return
            }
            let page = try await client.inbox(for: actual, filter: inboxFilter, offset: offset)
            identity = actual
            let seen = Set(items.map(\.caseId))
            items = offset == 0 ? page.items : items + page.items.filter { !seen.contains($0.caseId) }
            nextOffset = offset + page.items.count
            inboxSummary = page.summary; inboxAsOf = page.asOf
            hasMore = page.hasMore
            loaded = true
            error = nil
        } catch {
            // No fallback to the owner's global portfolio or stale company data.
            lifecycleMetrics = nil; lifecycleNotice = nil
            identity = nil
            items = []
            inboxSummary = nil; inboxAsOf = nil; nextOffset = 0
            hasMore = false
            loaded = false
            self.error = Self.safeError(error)
        }
    }

    func forget(_ id: String) {
        guard !isBusy, storageReady else { return }
        do {
            let updated = connections.filter { $0.id != id }
            try CompanyCredentialStore.save(updated)
            connections = updated
            if selectedID == id { resetSelection() }
        } catch { self.error = CompanyConnectionError.storage.localizedDescription }
    }

    func canDecide(accountID: String, caseID: String, revision: Int) -> Bool {
        guard selectedID == accountID, let identity, identity.legalAccepted,
              ["owner", "admin"].contains(identity.role) else { return false }
        return items.contains { $0.caseId == caseID && $0.revision == revision }
    }

    private func invalidateCompanyAccess() {
        identity = nil
        items = []
        inboxSummary = nil; inboxAsOf = nil; nextOffset = 0
        hasMore = false
        loaded = false
        pendingDecision = nil; pendingLifecycle = nil
        lifecycleMetrics = nil; lifecycleNotice = nil
    }

    func submitDecision(accountID: String, caseID: String, draft: CompanyDecisionDraft) async throws {
        guard !isBusy, let account = selected, canDecide(accountID: accountID, caseID: caseID, revision: draft.expectedRevision) else {
            throw CompanyConnectionError.http(409)
        }
        isBusy = true
        defer { isBusy = false }
        decisionNotice = nil
        lifecycleMetrics = nil
        let client = try CompanyAPIClient(connection: account)
        let actual: CompanyIdentity
        do {
            actual = try await client.verifiedIdentity(for: account.identity)
        } catch {
            invalidateCompanyAccess()
            self.error = Self.safeError(error)
            throw error
        }
        guard actual.legalAccepted, ["owner", "admin"].contains(actual.role) else {
            invalidateCompanyAccess()
            self.error = Self.safeError(CompanyConnectionError.http(403))
            throw CompanyConnectionError.http(403)
        }
        let attempt = CompanyDecisionAttempt.prepare(previous: pendingDecision, accountID: accountID, caseID: caseID, draft: draft)
        pendingDecision = attempt
        let saved: CompanyDecision
        do {
            saved = try await client.recordDecision(attempt, for: actual)
        } catch let failure as CompanyConnectionError {
            switch failure {
            case .http(409):
                pendingDecision = nil
                await load(account, offset: 0)
                throw failure
            case .http(401), .http(402), .http(403), .http(428), .identityMismatch:
                invalidateCompanyAccess()
                self.error = Self.safeError(failure)
                throw failure
            case .http(422), .invalidDecision:
                pendingDecision = nil
                throw failure
            default:
                throw CompanyConnectionError.decisionUncertain
            }
        } catch {
            throw CompanyConnectionError.decisionUncertain
        }
        pendingDecision = nil
        await load(account, offset: 0)
        decisionNotice = loaded ? "Решение сохранено · v\(saved.revision)" : "Решение сохранено · v\(saved.revision). Обновите портфель."
    }

    func evidence(for caseId: String) async throws -> CompanyEvidencePage {
        guard !isBusy, let account = selected, let identity, identity.legalAccepted,
              ["owner", "admin", "analyst"].contains(identity.role),
              items.contains(where: { $0.caseId == caseId }) else { throw CompanyConnectionError.identityMismatch }
        isBusy = true
        defer { isBusy = false }
        let client = try CompanyAPIClient(connection: account)
        let actual = try await client.verifiedIdentity(for: account.identity)
        guard actual.legalAccepted, ["owner", "admin", "analyst"].contains(actual.role) else { throw CompanyConnectionError.http(403) }
        return try await client.evidence(caseId: caseId)
    }

    private func lifecycleAccess(accountID: String, item: CompanyCase? = nil, write: Bool = false) async throws -> (CompanyAPIClient, CompanyIdentity) {
        guard let account = selected, account.id == accountID, identity?.legalAccepted == true,
              item.map({ choice in items.contains { $0.caseId == choice.caseId && $0.revision == choice.revision } }) ?? true else { throw CompanyConnectionError.http(409) }
        let client = try CompanyAPIClient(connection: account)
        let actual = try await client.verifiedIdentity(for: account.identity)
        guard actual.legalAccepted, !write || ["owner", "admin"].contains(actual.role) else { throw CompanyConnectionError.http(403) }
        identity = actual
        return (client, actual)
    }

    private func handleLifecycleError(_ failure: Error) {
        if let known = failure as? CompanyConnectionError {
            switch known {
            case .identityMismatch, .http(401), .http(402), .http(403), .http(428): invalidateCompanyAccess()
            default: break
            }
        }
        lifecycleMetrics = nil
    }

    func loadLifecycle(accountID: String, item: CompanyCase) async throws -> CompanyLifecycleState {
        guard !isBusy else { throw CompanyConnectionError.http(409) }
        isBusy = true; defer { isBusy = false }
        do {
            let (client, actual) = try await lifecycleAccess(accountID: accountID, item: item)
            return try await client.lifecycle(for: item, identity: actual)
        } catch { handleLifecycleError(error); throw error }
    }

    func loadLifecycleHistory(accountID: String, item: CompanyCase) async throws -> CompanyLifecycleHistory {
        guard !isBusy else { throw CompanyConnectionError.http(409) }
        isBusy = true; defer { isBusy = false }
        do {
            let (client, actual) = try await lifecycleAccess(accountID: accountID, item: item)
            return try await client.lifecycleHistory(caseID: item.caseId, identity: actual)
        } catch { handleLifecycleError(error); throw error }
    }

    func refreshLifecycleMetrics() async {
        guard !isBusy, let id = selectedID else { return }
        isBusy = true; defer { isBusy = false }
        lifecycleMetrics = nil; lifecycleNotice = nil
        do {
            let (client, actual) = try await lifecycleAccess(accountID: id)
            lifecycleMetrics = try await client.lifecycleMetrics(for: actual)
        } catch { handleLifecycleError(error); lifecycleNotice = Self.safeError(error) }
    }

    func submitLifecycle(accountID: String, item: CompanyCase, draft: CompanyLifecycleDraft) async throws -> CompanyLifecycleEvent {
        guard !isBusy, canDecide(accountID: accountID, caseID: item.caseId, revision: draft.expectedDecisionRevision) else { throw CompanyConnectionError.http(409) }
        isBusy = true; defer { isBusy = false }
        lifecycleMetrics = nil; lifecycleNotice = nil
        let client: CompanyAPIClient, actual: CompanyIdentity
        do { (client, actual) = try await lifecycleAccess(accountID: accountID, item: item, write: true) }
        catch { handleLifecycleError(error); throw error }
        let attempt = CompanyLifecycleAttempt.prepare(previous: pendingLifecycle, accountID: accountID, caseID: item.caseId, draft: draft)
        pendingLifecycle = attempt
        do {
            let saved = try await client.recordLifecycle(attempt, identity: actual)
            pendingLifecycle = nil
            return saved
        } catch let failure as CompanyConnectionError {
            switch failure {
            case .http(409), .http(422), .http(404): pendingLifecycle = nil; throw failure
            case .identityMismatch, .http(401), .http(402), .http(403), .http(428): handleLifecycleError(failure); throw failure
            default: throw CompanyConnectionError.lifecycleUncertain
            }
        } catch { throw CompanyConnectionError.lifecycleUncertain }
    }

    static func safeError(_ error: Error) -> String {
        if let known = error as? CompanyConnectionError { return known.localizedDescription }
        return "Не удалось получить данные компании. Проверьте подключение."
    }
}
