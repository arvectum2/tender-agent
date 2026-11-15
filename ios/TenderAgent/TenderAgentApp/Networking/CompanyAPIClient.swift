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
    case invalidOrigin, invalidToken, identityMismatch, invalidResponse, http(Int), storage, invalidDecision, decisionUncertain

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
