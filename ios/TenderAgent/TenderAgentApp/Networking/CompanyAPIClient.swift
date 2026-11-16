import Foundation

struct CompanyIdentity: Codable, Equatable, Sendable {
    let tenantId: String
    let customerId: String
    let memberId: String
    let companyName: String
    let role: String
    let legalAccepted: Bool

    func matchesAccount(_ expected: CompanyIdentity) -> Bool {
        tenantId == expected.tenantId && customerId == expected.customerId && memberId == expected.memberId
    }
}

struct CompanyConnection: Codable, Identifiable, Equatable, Sendable {
    let baseURL: URL
    let token: String
    let identity: CompanyIdentity

    var id: String { "\(baseURL.absoluteString)|\(identity.tenantId)|\(identity.memberId)" }
}

struct CompanyDecision: Codable, Sendable {
    let revision: Int
    let action: String
    let rationale: String
    let deferredUntil: Date?
    let decidedAt: Date
    let decidedByMemberId: String?
}

struct CompanyDecisionDraft: Equatable, Sendable {
    let action: String
    let rationale: String
    let deferredUntil: Date?
    let expectedRevision: Int

    init(action: String, rationale: String, deferredUntil: Date?, expectedRevision: Int, now: Date = Date()) throws {
        let text = rationale.trimmingCharacters(in: .whitespacesAndNewlines)
        guard ["GO", "NO_GO", "DEFER"].contains(action), !text.isEmpty,
              text.count <= 2000, expectedRevision >= 0 else { throw CompanyConnectionError.invalidDecision }
        let rounded = deferredUntil.map { Date(timeIntervalSince1970: floor($0.timeIntervalSince1970)) }
        if action == "DEFER" {
            guard let rounded, rounded > now else { throw CompanyConnectionError.invalidDecision }
        } else if rounded != nil { throw CompanyConnectionError.invalidDecision }
        self.action = action
        self.rationale = text
        self.deferredUntil = rounded
        self.expectedRevision = expectedRevision
    }
}

struct CompanyDecisionAttempt: Equatable, Sendable {
    let accountID: String
    let caseID: String
    let draft: CompanyDecisionDraft
    let key: String

    static func prepare(previous: Self?, accountID: String, caseID: String, draft: CompanyDecisionDraft) -> Self {
        if let previous, previous.accountID == accountID, previous.caseID == caseID, previous.draft == draft { return previous }
        return Self(accountID: accountID, caseID: caseID, draft: draft, key: UUID().uuidString)
    }

    struct Payload: Encodable {
        let action: String
        let rationale: String
        let deferredUntil: Date?
        let expectedRevision: Int
        let idempotencyKey: String
    }

    var payload: Payload {
        Payload(action: draft.action, rationale: draft.rationale, deferredUntil: draft.deferredUntil,
                expectedRevision: draft.expectedRevision, idempotencyKey: key)
    }

    func accepts(_ response: CompanyDecision, memberID: String) -> Bool {
        response.revision == draft.expectedRevision + 1 && response.action == draft.action &&
        response.rationale == draft.rationale && response.deferredUntil == draft.deferredUntil &&
        response.decidedByMemberId == memberID
    }
}

struct CompanyCase: Decodable, Identifiable, Sendable {
    let caseId: String
    let registryNumber: String?
    let sourcePlatform: String?
    let externalId: String?
    let sourceUrl: String?
    var displayReference: String { registryNumber ?? [sourcePlatform, externalId].compactMap { $0 }.joined(separator: ":") }
    var isCommercial: Bool { sourcePlatform != nil && sourcePlatform != "eis" }
    let sourceVerified: Bool
    let inboxState: String?
    let revision: Int
    let decision: CompanyDecision?
    var id: String { caseId }
}

struct CompanyPortfolioPage: Decodable, Sendable {
    let customerId: String
    let items: [CompanyCase]
    let hasMore: Bool

    func matchesCompany(_ identity: CompanyIdentity) -> Bool { customerId == identity.customerId }
}

enum CompanyInboxFilter: String, CaseIterable, Identifiable, Sendable {
    case attention, undecided, deferredDue = "deferred_due", deferredFuture = "deferred_future", go, noGo = "no_go", all
    var id: String { rawValue }
    var title: String {
        switch self {
        case .attention: "Требуют внимания"
        case .undecided: "Без решения"
        case .deferredDue: "Пора вернуться"
        case .deferredFuture: "Отложены"
        case .go: "GO"
        case .noGo: "NO GO"
        case .all: "Все закупки"
        }
    }
}

struct CompanyInboxSummary: Decodable, Sendable {
    let undecided: Int
    let deferredDue: Int
    let deferredFuture: Int
    let go: Int
    let noGo: Int
    let attention: Int
    let all: Int

    var valid: Bool {
        let counts = [undecided, deferredDue, deferredFuture, go, noGo, attention, all]
        return counts.allSatisfy { $0 >= 0 && $0 <= Int.max / 8 } &&
            attention == undecided + deferredDue && all == undecided + deferredDue + deferredFuture + go + noGo
    }
}

struct CompanyInboxPage: Decodable, Sendable {
    let customerId: String
    let asOf: Date
    let view: String
    let offset: Int
    let limit: Int
    let summary: CompanyInboxSummary
    let items: [CompanyCase]
    let hasMore: Bool
    let scope: String
    let marketCoverageComplete: Bool
    let liveDeadlineVerified: Bool
    let externalSubmissionAllowed: Bool

    func matches(_ identity: CompanyIdentity, filter: CompanyInboxFilter, offset expectedOffset: Int) -> Bool {
        guard customerId == identity.customerId, view == filter.rawValue, offset == expectedOffset,
              scope == "SAVED_COMPANY_REFERENCES_AND_HUMAN_DECISIONS", !externalSubmissionAllowed,
              !marketCoverageComplete, !liveDeadlineVerified, summary.valid, limit == 50,
              items.count <= limit, Set(items.map(\.caseId)).count == items.count,
              !hasMore || items.count == limit else { return false }
        return items.allSatisfy { item in
            let state: String
            if let action = item.decision {
                guard item.revision == action.revision else { return false }
                switch action.action {
                case "GO": state = "go"
                case "NO_GO": state = "no_go"
                case "DEFER":
                    guard let due = action.deferredUntil else { return false }
                    state = due <= asOf ? "deferred_due" : "deferred_future"
                default: return false
                }
            } else {
                guard item.revision == 0 else { return false }
                state = "undecided"
            }
            return item.inboxState == state && (filter == .all || (filter == .attention ? ["undecided", "deferred_due"].contains(state) : filter.rawValue == state))
        }
    }
}

enum CompanyLifecycleStage: String, Codable, CaseIterable, Identifiable, Sendable {
    case preparing = "PREPARING", blocked = "BLOCKED", ready = "READY", submitted = "SUBMITTED"
    case won = "WON", lost = "LOST", rejected = "REJECTED", withdrawn = "WITHDRAWN", cancelled = "CANCELLED"
    var id: String { rawValue }
    var isPreparation: Bool { [.preparing, .blocked, .ready].contains(self) }
    var isOutcome: Bool { !isPreparation && self != .submitted }
    var title: String {
        switch self {
        case .preparing: "Подготовка"
        case .blocked: "Заблокирована"
        case .ready: "Готовность подтверждена сотрудником"
        case .submitted: "Подача зарегистрирована"
        case .won: "Победа"
        case .lost: "Проигрыш"
        case .rejected: "Отклонена"
        case .withdrawn: "Отозвана"
        case .cancelled: "Отменена"
        }
    }
}

struct CompanyLifecycleDraft: Codable, Equatable, Sendable {
    let stage: CompanyLifecycleStage
    let rationale: String
    let sourceRef: String?
    let occurredAt: Date?
    let expectedRevision: Int
    let expectedDecisionRevision: Int
    let correctOutcome: Bool

    init(stage: CompanyLifecycleStage, rationale: String, sourceRef: String?, occurredAt: Date?, state: CompanyLifecycleState, now: Date = Date()) throws {
        let text = rationale.trimmingCharacters(in: .whitespacesAndNewlines)
        let ref = sourceRef?.trimmingCharacters(in: .whitespacesAndNewlines)
        let date = occurredAt.map { Date(timeIntervalSince1970: floor($0.timeIntervalSince1970)) }
        guard state.options.contains(stage), !text.isEmpty, text.count <= 2000 else { throw CompanyConnectionError.invalidLifecycle }
        if stage.isPreparation {
            guard ref == nil, date == nil else { throw CompanyConnectionError.invalidLifecycle }
        } else {
            guard let ref, !ref.isEmpty, ref.count <= 500, let date, date <= now else { throw CompanyConnectionError.invalidLifecycle }
        }
        self.stage = stage; self.rationale = text; self.sourceRef = ref; self.occurredAt = date
        expectedRevision = state.revision; expectedDecisionRevision = state.decisionRevision
        correctOutcome = state.latest?.stage.isOutcome == true
    }
}

struct CompanyLifecycleAttestation: Codable, Equatable, Sendable {
    let stage: CompanyLifecycleStage
    let rationale: String
    let sourceRef: String?
    let occurredAt: Date?
    let expectedRevision: Int
    let expectedDecisionRevision: Int
    let correctOutcome: Bool
    let idempotencyKey: String

    init(draft: CompanyLifecycleDraft, key: String) {
        stage = draft.stage; rationale = draft.rationale; sourceRef = draft.sourceRef; occurredAt = draft.occurredAt
        expectedRevision = draft.expectedRevision; expectedDecisionRevision = draft.expectedDecisionRevision
        correctOutcome = draft.correctOutcome; idempotencyKey = key
    }
}

struct CompanyLifecycleEvent: Decodable, Identifiable, Sendable {
    let eventId: String
    let caseId: String
    let revision: Int
    let stage: CompanyLifecycleStage
    let memberId: String
    let createdAt: Date
    let attestation: CompanyLifecycleAttestation
    let readinessStale: Bool
    let origin: String
    let externalFactVerified: Bool
    let externalSubmissionAllowed: Bool
    var id: String { eventId }
    func matches(caseID: String) -> Bool {
        caseId == caseID && revision > 0 && revision <= 50 && origin == "HUMAN_ATTESTATION" &&
        !externalFactVerified && !externalSubmissionAllowed && attestation.stage == stage && attestation.expectedRevision == revision - 1
    }
}

struct CompanyLifecycleState: Decodable, Sendable {
    let customerId: String
    let caseId: String
    let decisionRevision: Int
    let decisionAction: String?
    let revision: Int
    let latest: CompanyLifecycleEvent?
    let externalSubmissionAllowed: Bool
    func matches(_ identity: CompanyIdentity, item: CompanyCase) -> Bool {
        customerId == identity.customerId && caseId == item.caseId && !externalSubmissionAllowed &&
        decisionRevision == item.revision && decisionAction == item.decision?.action &&
        (0...50).contains(revision) && (revision == 0 ? latest == nil : latest?.matches(caseID: caseId) == true && latest?.revision == revision)
    }
    var options: [CompanyLifecycleStage] {
        guard revision < 50, decisionRevision > 0 else { return [] }
        if latest?.stage == .submitted { return CompanyLifecycleStage.allCases.filter(\.isOutcome) }
        if let stage = latest?.stage, stage.isOutcome { return CompanyLifecycleStage.allCases.filter { $0.isOutcome && $0 != stage } }
        guard decisionAction == "GO" else { return [] }
        return [.preparing, .blocked, .ready] + (latest?.stage == .ready && latest?.readinessStale == false ? [.submitted] : [])
    }
}

struct CompanyLifecycleAttempt: Equatable, Sendable {
    let accountID: String
    let caseID: String
    let draft: CompanyLifecycleDraft
    let key: String
    static func prepare(previous: Self?, accountID: String, caseID: String, draft: CompanyLifecycleDraft) -> Self {
        if let previous, previous.accountID == accountID, previous.caseID == caseID, previous.draft == draft { return previous }
        return Self(accountID: accountID, caseID: caseID, draft: draft, key: UUID().uuidString)
    }
    var payload: CompanyLifecycleAttestation { .init(draft: draft, key: key) }
    func accepts(_ event: CompanyLifecycleEvent, memberID: String) -> Bool {
        event.matches(caseID: caseID) && event.memberId == memberID && event.attestation == payload
    }
}

struct CompanyLifecycleHistory: Decodable, Sendable {
    let customerId: String
    let caseId: String
    let items: [CompanyLifecycleEvent]
    let hasMore: Bool
    let externalSubmissionAllowed: Bool
    func matches(_ identity: CompanyIdentity, caseID: String) -> Bool {
        customerId == identity.customerId && caseId == caseID && !externalSubmissionAllowed && items.count <= 50 && items.allSatisfy { $0.matches(caseID: caseID) } && Set(items.map(\.revision)).count == items.count
    }
}

struct CompanyLifecycleRate: Decodable, Sendable {
    let numerator: Int
    let denominator: Int
    let rate: Double?
    var valid: Bool {
        numerator >= 0 && denominator >= numerator && (denominator == 0 ? rate == nil : rate.map { $0.isFinite && abs($0 - Double(numerator)/Double(denominator)) < 1e-9 } == true)
    }
    var display: String { rate.map { String(format: "%.1f%%", $0*100) + " (\(numerator)/\(denominator))" } ?? "Нет данных" }
}

struct CompanyLifecycleMetrics: Decodable, Sendable {
    let customerId: String
    let asOf: Date
    let scope: String
    let savedCases: Int
    let everGoCases: Int
    let recordedSubmissions: Int
    let stageCounts: [String: Int]
    let goToSubmission: CompanyLifecycleRate
    let winRate: CompanyLifecycleRate
    let externalFactsVerified: Bool
    let marketCoverageComplete: Bool
    let contractRevenueVerified: Bool
    func matches(_ identity: CompanyIdentity) -> Bool {
        let stages = Set(CompanyLifecycleStage.allCases.map(\.rawValue) + ["UNRECORDED"])
        guard customerId == identity.customerId, scope == "ALL_TIME_SAVED_CASES_HUMAN_ATTESTATIONS", !externalFactsVerified, !marketCoverageComplete, !contractRevenueVerified,
              Set(stageCounts.keys) == stages, stageCounts.values.allSatisfy({ $0 >= 0 && $0 <= Int.max/16 }),
              savedCases == stageCounts.values.reduce(0,+), savedCases >= everGoCases, everGoCases >= recordedSubmissions, recordedSubmissions >= 0,
              goToSubmission.valid, winRate.valid, goToSubmission.numerator == recordedSubmissions, goToSubmission.denominator == everGoCases else { return false }
        let submissions = CompanyLifecycleStage.allCases.filter { !$0.isPreparation }.reduce(0) { $0 + (stageCounts[$1.rawValue] ?? 0) }
        return submissions == recordedSubmissions && winRate.numerator == stageCounts["WON"] && winRate.denominator == ["WON","LOST","REJECTED"].reduce(0) { $0 + (stageCounts[$1] ?? 0) }
    }
}

struct CompanyEvidence: Decodable, Identifiable, Sendable {
    let bindingId: String
    let caseId: String
    let runId: String
    let profileVersion: Int
    let currentProfileVersion: Int?
    let profileState: String
    var id: String { bindingId }
}

struct CompanyEvidencePage: Decodable, Sendable {
    let items: [CompanyEvidence]
    let hasMore: Bool
}

enum CompanyConnectionError: LocalizedError {
    case invalidOrigin, invalidToken, identityMismatch, invalidResponse, http(Int), storage, invalidDecision, decisionUncertain, invalidLifecycle, lifecycleUncertain

    var errorDescription: String? {
        switch self {
        case .invalidOrigin: "Нужен доверенный HTTPS-адрес сервера без пути и параметров."
        case .invalidToken: "Требуется действующий токен компании saas_…"
        case .identityMismatch: "Компания или участник не совпадают. Доступ остановлен."
        case .invalidResponse: "Некорректный ответ сервера."
        case .http(401): "Токен истёк или отозван. Подключитесь повторно."
        case .http(402): "Доступ компании по текущему пакету завершён."
        case .http(403): "Доступ запрещён для этой роли или компании."
        case .http(428): "Подтвердите условия пилота в веб-кабинете."
        case .storage: "Не удалось сохранить подключения в Keychain."
        case .invalidDecision: "Укажите действие, обоснование и будущую дату отсрочки, если она нужна."
        case .invalidLifecycle: "Проверьте допустимое состояние, обоснование, ссылку и дату события."
        case .lifecycleUncertain: "Ответ о записи не получен. Проверьте журнал или повторите ту же запись."
        case .decisionUncertain: "Ответ о сохранении не получен. Проверьте карточку или явно повторите то же решение."
        case .http(409): "Решение уже изменилось. Откройте обновлённую карточку и подтвердите заново."
        case let .http(code): "Сервер вернул HTTP \(code)."
        }
    }
}

final class CompanyNoRedirect: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest,
                    completionHandler: @escaping @Sendable (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}

struct CompanyAPIClient: Sendable {
    let baseURL: URL
    private let token: String
    private let session: URLSession

    static func validatedOrigin(_ input: String) throws -> URL {
        guard var parts = URLComponents(string: input.trimmingCharacters(in: .whitespacesAndNewlines)),
              parts.scheme?.lowercased() == "https", let host = parts.host, !host.isEmpty,
              parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil,
              parts.path == "" || parts.path == "/" else { throw CompanyConnectionError.invalidOrigin }
        parts.scheme = "https"
        parts.host = host.lowercased()
        parts.path = ""
        if parts.port == 443 { parts.port = nil }
        guard let result = parts.url else { throw CompanyConnectionError.invalidOrigin }
        return result
    }

    init(origin: String, token: String, session: URLSession? = nil) throws {
        baseURL = try Self.validatedOrigin(origin)
        guard token.hasPrefix("saas_"), token.count <= 160, token.count > 20,
              token.utf8.allSatisfy({ (65...90).contains($0) || (97...122).contains($0) || (48...57).contains($0) || $0 == 95 || $0 == 45 }) else {
            throw CompanyConnectionError.invalidToken
        }
        self.token = token
        let config = URLSessionConfiguration.ephemeral
        config.urlCache = nil
        config.httpCookieStorage = nil
        config.httpShouldSetCookies = false
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        self.session = session ?? URLSession(configuration: config, delegate: CompanyNoRedirect(), delegateQueue: nil)
    }

    init(connection: CompanyConnection, session: URLSession? = nil) throws {
        try self.init(origin: connection.baseURL.absoluteString, token: connection.token, session: session)
    }

    func identity() async throws -> CompanyIdentity { try await get("api/saas/me") }

    func verifiedIdentity(for expected: CompanyIdentity) async throws -> CompanyIdentity {
        let actual = try await identity()
        guard actual.matchesAccount(expected) else { throw CompanyConnectionError.identityMismatch }
        return actual
    }

    func portfolio(for identity: CompanyIdentity, offset: Int = 0) async throws -> CompanyPortfolioPage {
        let page: CompanyPortfolioPage = try await get("api/saas/company-portfolio/cases", query: [URLQueryItem(name: "offset", value: String(offset))])
        guard page.matchesCompany(identity) else { throw CompanyConnectionError.identityMismatch }
        return page
    }

    func inbox(for identity: CompanyIdentity, filter: CompanyInboxFilter, offset: Int = 0) async throws -> CompanyInboxPage {
        let page: CompanyInboxPage = try await get("api/saas/company-portfolio/manager-inbox", query: [
            URLQueryItem(name: "view", value: filter.rawValue), URLQueryItem(name: "offset", value: String(offset)), URLQueryItem(name: "limit", value: "50")])
        guard page.matches(identity, filter: filter, offset: offset) else { throw CompanyConnectionError.identityMismatch }
        return page
    }

    func evidence(caseId: String) async throws -> CompanyEvidencePage {
        guard UUID(uuidString: caseId) != nil else { throw CompanyConnectionError.invalidResponse }
        let page: CompanyEvidencePage = try await get("api/saas/company-portfolio/cases/\(caseId)/evidence")
        guard page.items.allSatisfy({ $0.caseId == caseId }) else { throw CompanyConnectionError.identityMismatch }
        return page
    }

    func recordDecision(_ attempt: CompanyDecisionAttempt, for identity: CompanyIdentity) async throws -> CompanyDecision {
        guard UUID(uuidString: attempt.caseID) != nil else { throw CompanyConnectionError.invalidResponse }
        guard identity.legalAccepted, ["owner", "admin"].contains(identity.role) else { throw CompanyConnectionError.http(403) }
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        let result: CompanyDecision = try await get("api/saas/company-portfolio/cases/\(attempt.caseID)/decisions",
                                                   method: "POST", body: encoder.encode(attempt.payload))
        guard attempt.accepts(result, memberID: identity.memberId) else { throw CompanyConnectionError.decisionUncertain }
        return result
    }

    func lifecycle(for item: CompanyCase, identity: CompanyIdentity) async throws -> CompanyLifecycleState {
        guard UUID(uuidString: item.caseId) != nil else { throw CompanyConnectionError.invalidResponse }
        let state: CompanyLifecycleState = try await get("api/saas/company-portfolio/cases/\(item.caseId)/lifecycle")
        guard state.customerId == identity.customerId, state.caseId == item.caseId else { throw CompanyConnectionError.identityMismatch }
        guard state.decisionRevision == item.revision else { throw CompanyConnectionError.http(409) }
        guard state.matches(identity, item: item) else { throw CompanyConnectionError.identityMismatch }
        return state
    }

    func lifecycleHistory(caseID: String, identity: CompanyIdentity) async throws -> CompanyLifecycleHistory {
        guard UUID(uuidString: caseID) != nil else { throw CompanyConnectionError.invalidResponse }
        let result: CompanyLifecycleHistory = try await get("api/saas/company-portfolio/cases/\(caseID)/lifecycle/history")
        guard result.matches(identity, caseID: caseID) else { throw CompanyConnectionError.identityMismatch }
        return result
    }

    func lifecycleMetrics(for identity: CompanyIdentity) async throws -> CompanyLifecycleMetrics {
        let result: CompanyLifecycleMetrics = try await get("api/saas/company-portfolio/lifecycle-metrics")
        guard result.matches(identity) else { throw CompanyConnectionError.identityMismatch }
        return result
    }

    func recordLifecycle(_ attempt: CompanyLifecycleAttempt, identity: CompanyIdentity) async throws -> CompanyLifecycleEvent {
        guard UUID(uuidString: attempt.caseID) != nil else { throw CompanyConnectionError.invalidResponse }
        guard identity.legalAccepted, ["owner", "admin"].contains(identity.role) else { throw CompanyConnectionError.http(403) }
        let encoder = JSONEncoder(); encoder.keyEncodingStrategy = .convertToSnakeCase; encoder.dateEncodingStrategy = .iso8601
        let event: CompanyLifecycleEvent = try await get("api/saas/company-portfolio/cases/\(attempt.caseID)/lifecycle", method: "POST", body: encoder.encode(attempt.payload))
        guard attempt.accepts(event, memberID: identity.memberId) else { throw CompanyConnectionError.identityMismatch }
        return event
    }

    private func get<T: Decodable>(_ path: String, query: [URLQueryItem] = [], method: String = "GET", body: Data? = nil) async throws -> T {
        guard var parts = URLComponents(url: baseURL.appending(path: path), resolvingAgainstBaseURL: false) else { throw CompanyConnectionError.invalidOrigin }
        if !query.isEmpty { parts.queryItems = query }
        guard let url = parts.url else { throw CompanyConnectionError.invalidOrigin }
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
        request.httpMethod = method
        request.httpBody = body
        if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw CompanyConnectionError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw CompanyConnectionError.http(http.statusCode) }
        return try TenderAgentJSON.makeDecoder().decode(T.self, from: data)
    }
}
