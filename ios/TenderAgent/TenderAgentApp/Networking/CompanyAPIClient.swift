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
}

struct CompanyCase: Decodable, Identifiable, Sendable {
    let caseId: String
    let registryNumber: String?
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
    case invalidOrigin, invalidToken, identityMismatch, invalidResponse, http(Int), storage

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
        case let .http(code): "Сервер вернул HTTP \(code)."
        case .storage: "Не удалось сохранить подключения в Keychain."
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

    private func get<T: Decodable>(_ path: String, query: [URLQueryItem] = []) async throws -> T {
        guard var parts = URLComponents(url: baseURL.appending(path: path), resolvingAgainstBaseURL: false) else { throw CompanyConnectionError.invalidOrigin }
        if !query.isEmpty { parts.queryItems = query }
        guard let url = parts.url else { throw CompanyConnectionError.invalidOrigin }
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw CompanyConnectionError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw CompanyConnectionError.http(http.statusCode) }
        return try TenderAgentJSON.makeDecoder().decode(T.self, from: data)
    }
}
