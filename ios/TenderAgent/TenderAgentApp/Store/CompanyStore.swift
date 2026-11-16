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
    @Published private(set) var actualSamples: [CompanyActualSampleSelection] = []
    @Published private(set) var actualSampleResult: CompanyActualSamplePreview?
    @Published private(set) var actualSampleNotice: String?
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
        clearActualSamples()
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
                if identity != actual { clearActualSamples() }
                identity = actual
                items = []
                inboxSummary = nil; inboxAsOf = nil; nextOffset = 0
                hasMore = false
                loaded = false
                return
            }
            let page = try await client.inbox(for: actual, filter: inboxFilter, offset: offset)
            if identity != actual { clearActualSamples() }
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
            clearActualSamples()
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
        clearActualSamples()
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
        if identity != actual { clearActualSamples() }
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

    func readiness(accountID: String, item: CompanyCase, event: CompanyLifecycleEvent, bind: CompanyReadinessBinding? = nil) async throws -> CompanyReadinessBinding {
        guard !isBusy else { throw CompanyConnectionError.http(409) }
        isBusy = true; defer { isBusy = false }
        do {
            let (client, actual) = try await lifecycleAccess(accountID: accountID, item: item, write: bind != nil)
            return try await client.readiness(item: item, event: event, identity: actual, bind: bind)
        } catch { handleLifecycleError(error); throw error }
    }

    func eventArtifact(accountID: String, item: CompanyCase, event: CompanyLifecycleEvent, upload: CompanyArtifactBytes? = nil) async throws -> CompanyEventArtifact {
        guard !isBusy else { throw CompanyConnectionError.http(409) }
        isBusy = true; defer { isBusy = false }
        do {
            let (client, actual) = try await lifecycleAccess(accountID: accountID, item: item, write: upload != nil)
            return try await client.eventArtifact(item: item, event: event, identity: actual, upload: upload)
        } catch { handleLifecycleError(error); throw error }
    }

    func downloadEventArtifact(accountID: String, item: CompanyCase, event: CompanyLifecycleEvent, artifact: CompanyEventArtifact) async throws -> CompanyArtifactBytes {
        guard !isBusy else { throw CompanyConnectionError.http(409) }
        isBusy = true; defer { isBusy = false }
        do {
            let (client, actual) = try await lifecycleAccess(accountID: accountID, item: item)
            return try await client.downloadEventArtifact(item: item, event: event, identity: actual, artifact: artifact)
        } catch { handleLifecycleError(error); throw error }
    }

    func costBinding(accountID: String,item: CompanyCase,target: CompanyCostTarget) async throws -> CompanyCostBinding {
        guard !isBusy else { throw CompanyConnectionError.http(409) }; isBusy=true; defer { isBusy=false }
        do { let (client,actual)=try await lifecycleAccess(accountID:accountID,item:item); return try await client.costBinding(caseID:item.caseId,identity:actual,target:target) }
        catch { handleLifecycleError(error); throw error }
    }
    func saveCostEvidence(accountID: String,item: CompanyCase,target: CompanyCostTarget,binding: CompanyCostBinding,kind: CompanyCostDocumentKind,bytes: CompanyArtifactBytes) async throws -> CompanyCostEvidence {
        guard !isBusy else { throw CompanyConnectionError.http(409) }; isBusy=true; defer { isBusy=false }
        do { let (client,actual)=try await lifecycleAccess(accountID:accountID,item:item,write:true); return try await client.saveCostEvidence(caseID:item.caseId,identity:actual,target:target,binding:binding,kind:kind,bytes:bytes) }
        catch { handleLifecycleError(error); throw error }
    }
    func downloadCostEvidence(accountID: String,item: CompanyCase,target: CompanyCostTarget,evidence: CompanyCostEvidence) async throws -> CompanyArtifactBytes {
        guard !isBusy else { throw CompanyConnectionError.http(409) }; isBusy=true; defer { isBusy=false }
        do { let (client,actual)=try await lifecycleAccess(accountID:accountID,item:item); return try await client.downloadCostEvidence(caseID:item.caseId,identity:actual,target:target,evidence:evidence) }
        catch { handleLifecycleError(error); throw error }
    }

    func pricePreview(accountID: String, item: CompanyCase, input: CompanyPriceInput) async throws -> CompanyPricePreview {
        guard !isBusy else { throw CompanyConnectionError.http(409) }
        isBusy = true; defer { isBusy = false }
        do {
            let (client, actual) = try await lifecycleAccess(accountID: accountID, item: item)
            return try await client.pricePreview(caseID: item.caseId, identity: actual, input: input)
        } catch { handleLifecycleError(error); throw error }
    }

    func itemizedPreview(accountID: String, item: CompanyCase, estimate: CompanyItemizedInput) async throws -> CompanyItemizedPreview {
        guard !isBusy else { throw CompanyConnectionError.http(409) }
        isBusy=true; defer { isBusy=false }
        do {
            let (client,actual)=try await lifecycleAccess(accountID:accountID,item:item)
            return try await client.itemizedPreview(caseID:item.caseId,identity:actual,estimate:estimate)
        } catch { handleLifecycleError(error); throw error }
    }

    func priceHistory(accountID: String, item: CompanyCase) async throws -> CompanyPriceHistory {
        guard !isBusy else { throw CompanyConnectionError.http(409) }
        isBusy = true; defer { isBusy = false }
        do {
            let (client, actual) = try await lifecycleAccess(accountID: accountID, item: item)
            return try await client.priceHistory(caseID:item.caseId,identity:actual)
        } catch { handleLifecycleError(error); throw error }
    }

    func savePrice(accountID: String, item: CompanyCase, attempt: CompanyPriceAttempt) async throws -> CompanyPriceRecord {
        guard !isBusy, accountID == attempt.accountID, item.caseId == attempt.caseID, canDecide(accountID: accountID, caseID: item.caseId, revision: item.revision) else { throw CompanyConnectionError.http(409) }
        isBusy = true; defer { isBusy = false }
        let client: CompanyAPIClient, actual: CompanyIdentity
        do { (client, actual) = try await lifecycleAccess(accountID: accountID, item: item, write:true) }
        catch { handleLifecycleError(error); throw error }
        do { return try await client.savePrice(attempt,identity:actual) }
        catch let failure as CompanyConnectionError {
            switch failure {
            case .http(409), .http(422), .http(404): throw failure
            case .identityMismatch, .http(401), .http(402), .http(403), .http(428): handleLifecycleError(failure); throw failure
            default: throw CompanyConnectionError.priceUncertain
            }
        } catch { throw CompanyConnectionError.priceUncertain }
    }

    func actualHistory(accountID:String,item:CompanyCase,baseline:CompanyActualBaseline) async throws -> [CompanyActualRecord] {
        guard !isBusy else {throw CompanyConnectionError.http(409)};isBusy=true;defer {isBusy=false}
        do {let (client,actual)=try await lifecycleAccess(accountID:accountID,item:item);return try await client.actualHistory(caseID:item.caseId,identity:actual,baseline:baseline)} catch {handleLifecycleError(error);throw error}
    }
    func actualPreview(accountID:String,item:CompanyCase,baseline:CompanyActualBaseline,input:CompanyActualInput) async throws -> CompanyActualPreview {
        guard !isBusy else {throw CompanyConnectionError.http(409)};isBusy=true;defer {isBusy=false}
        do {let (client,actual)=try await lifecycleAccess(accountID:accountID,item:item);return try await client.actualPreview(caseID:item.caseId,identity:actual,baseline:baseline,input:input)} catch {handleLifecycleError(error);throw error}
    }
    func saveActual(accountID:String,item:CompanyCase,baseline:CompanyActualBaseline,attempt:CompanyActualAttempt) async throws -> CompanyActualRecord {
        guard !isBusy,accountID==attempt.accountID,canDecide(accountID:accountID,caseID:item.caseId,revision:item.revision) else {throw CompanyConnectionError.http(409)};isBusy=true;defer {isBusy=false}
        do {let (client,actual)=try await lifecycleAccess(accountID:accountID,item:item,write:true);return try await client.saveActual(caseID:item.caseId,identity:actual,baseline:baseline,attempt:attempt)} catch {handleLifecycleError(error);throw error}
    }

    func actualEvidenceBinding(accountID:String,item:CompanyCase,target:CompanyActualEvidenceTarget) async throws -> CompanyActualEvidenceBinding {
        guard !isBusy else {throw CompanyConnectionError.http(409)};isBusy=true;defer {isBusy=false}
        do {let (client,actual)=try await lifecycleAccess(accountID:accountID,item:item);return try await client.actualEvidenceBinding(caseID:item.caseId,identity:actual,target:target)} catch {handleLifecycleError(error);throw error}
    }
    func saveActualEvidence(accountID:String,item:CompanyCase,target:CompanyActualEvidenceTarget,binding:CompanyActualEvidenceBinding,kind:CompanyActualDocumentKind,bytes:CompanyArtifactBytes) async throws -> CompanyActualEvidence {
        guard !isBusy,canDecide(accountID:accountID,caseID:item.caseId,revision:item.revision) else {throw CompanyConnectionError.http(409)};isBusy=true;defer {isBusy=false}
        do {let (client,actual)=try await lifecycleAccess(accountID:accountID,item:item,write:true);return try await client.saveActualEvidence(caseID:item.caseId,identity:actual,target:target,binding:binding,kind:kind,bytes:bytes)} catch {handleLifecycleError(error);throw error}
    }
    func downloadActualEvidence(accountID:String,item:CompanyCase,target:CompanyActualEvidenceTarget,evidence:CompanyActualEvidence) async throws -> CompanyArtifactBytes {
        guard !isBusy else {throw CompanyConnectionError.http(409)};isBusy=true;defer {isBusy=false}
        do {let (client,actual)=try await lifecycleAccess(accountID:accountID,item:item);return try await client.downloadActualEvidence(caseID:item.caseId,identity:actual,target:target,evidence:evidence)} catch {handleLifecycleError(error);throw error}
    }

    var canCompareActualSamples: Bool {
        identity?.legalAccepted == true && ["owner","admin","analyst"].contains(identity?.role ?? "")
    }

    func invalidateActualSampleResult() {
        actualSampleResult=nil;actualSampleNotice=nil
    }

    func clearActualSamples() {
        actualSamples=[];invalidateActualSampleResult()
    }
    func removeActualSample(_ id:String) {
        guard !isBusy,canCompareActualSamples else{return}
        actualSamples.removeAll{$0.sample.id==id};invalidateActualSampleResult()
    }
    func addActualSample(accountID:String,item:CompanyCase,target:CompanyActualEvidenceTarget,latestSnapshotID:String) {
        guard !isBusy,canCompareActualSamples,selectedID==accountID,let identity,items.contains(where:{$0.caseId==item.caseId && $0.revision==item.revision}) else{return}
        do {
            let row=try CompanyActualSampleSelection.make(identity:identity,item:item,target:target,latestSnapshotID:latestSnapshotID)
            _=try CompanyActualSampleInput.make(actualSamples+[row],comparable:true,distinct:true)
            actualSamples.append(row);invalidateActualSampleResult()
        } catch {
            actualSampleNotice="Выберите последнюю заявленную строку с положительным количеством, без повторной закупки и с той же работой, категорией и единицей."
        }
    }
    func previewActualSamples(comparable:Bool,distinct:Bool) async {
        guard !isBusy,canCompareActualSamples,let accountID=selectedID,let current=identity else{return}
        let rows=actualSamples
        invalidateActualSampleResult()
        isBusy=true;defer{isBusy=false}
        do {
            let (client,actual)=try await lifecycleAccess(accountID:accountID)
            guard actual==current,actualSamples==rows else{throw CompanyConnectionError.identityMismatch}
            let result=try await client.actualSamplePreview(identity:actual,selections:rows,comparable:comparable,distinct:distinct)
            guard selectedID==accountID,identity==actual,actualSamples==rows else{throw CompanyConnectionError.identityMismatch}
            actualSampleResult=result
            actualSampleNotice="Предварительное сравнение. Не сохранено."
        } catch CompanyConnectionError.http(409) {
            actualSampleNotice="Срез устарел. Исключите его и выберите актуальный."
        } catch CompanyConnectionError.http(404) {
            actualSampleNotice="Функция недоступна или строка не найдена."
        } catch {
            handleLifecycleError(error)
            if canCompareActualSamples { actualSampleNotice=Self.safeError(error) }
        }
    }

    static func safeError(_ error: Error) -> String {
        if let known = error as? CompanyConnectionError { return known.localizedDescription }
        return "Не удалось получить данные компании. Проверьте подключение."
    }
}
