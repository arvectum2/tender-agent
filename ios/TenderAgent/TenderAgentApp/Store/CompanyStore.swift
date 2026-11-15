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
    private var pendingDecision: CompanyDecisionAttempt?

    init() {
        do {
            connections = try CompanyCredentialStore.load()
            storageReady = true
        } catch { self.error = CompanyConnectionError.storage.localizedDescription }
    }

    private var selected: CompanyConnection? { connections.first { $0.id == selectedID } }

    private func resetSelection(_ id: String? = nil) {
        if selectedID != id { pendingDecision = nil }
        selectedID = id
        decisionNotice = nil
        identity = nil
        items = []
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
        await load(account, offset: items.count)
    }

    private func load(_ account: CompanyConnection, offset: Int) async {
        do {
            let client = try CompanyAPIClient(connection: account)
            let actual = try await client.verifiedIdentity(for: account.identity)
            guard actual.legalAccepted else {
                identity = actual
                items = []
                hasMore = false
                loaded = false
                return
            }
            let page = try await client.portfolio(for: actual, offset: offset)
            identity = actual
            items = offset == 0 ? page.items : items + page.items
            hasMore = page.hasMore
            loaded = true
            error = nil
        } catch {
            // No fallback to the owner's global portfolio or stale company data.
            identity = nil
            items = []
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
        hasMore = false
        loaded = false
        pendingDecision = nil
    }

    func submitDecision(accountID: String, caseID: String, draft: CompanyDecisionDraft) async throws {
        guard !isBusy, let account = selected, canDecide(accountID: accountID, caseID: caseID, revision: draft.expectedRevision) else {
            throw CompanyConnectionError.http(409)
        }
        isBusy = true
        defer { isBusy = false }
        decisionNotice = nil
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

    static func safeError(_ error: Error) -> String {
        if let known = error as? CompanyConnectionError { return known.localizedDescription }
        return "Не удалось получить данные компании. Проверьте подключение."
    }
}
