import Foundation

struct TenderAgentAPIConfiguration {
    let baseURL: URL
    let username: String
    let password: String

    static func fromEnvironment(
        _ environment: [String: String] = ProcessInfo.processInfo.environment
    ) -> TenderAgentAPIConfiguration? {
        guard
            let rawURL = environment["TENDER_AGENT_API_BASE_URL"],
            let baseURL = URL(string: rawURL),
            let username = environment["TENDER_AGENT_API_USERNAME"],
            let password = environment["TENDER_AGENT_API_PASSWORD"],
            !username.isEmpty,
            !password.isEmpty
        else {
            return nil
        }
        return TenderAgentAPIConfiguration(
            baseURL: baseURL,
            username: username,
            password: password
        )
    }
}

enum TenderAgentAPIError: LocalizedError {
    case invalidResponse
    case httpStatus(Int, String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Некорректный ответ backend."
        case let .httpStatus(code, body):
            return "Backend вернул HTTP \(code): \(body)"
        }
    }
}

struct TenderAgentAPIClient {
    let configuration: TenderAgentAPIConfiguration
    let session: URLSession

    init(
        configuration: TenderAgentAPIConfiguration,
        session: URLSession = .shared
    ) {
        self.configuration = configuration
        self.session = session
    }

    static func preferred() -> TenderAgentAPIClient? {
        let environment = ProcessInfo.processInfo.environment
        if let configuration = TenderAgentAPIConfiguration.fromEnvironment(environment) {
            if environment["TENDER_AGENT_PERSIST_ENV"] == "1" {
                try? BackendCredentialStore.save(
                    baseURLString: configuration.baseURL.absoluteString,
                    username: configuration.username,
                    password: configuration.password
                )
            }
            return TenderAgentAPIClient(configuration: configuration)
        }
        guard let configuration = BackendCredentialStore.loadConfiguration() else {
            return nil
        }
        return TenderAgentAPIClient(configuration: configuration)
    }

    func fetchPortfolio() async throws -> MobilePortfolioEnvelope {
        try await request(path: "mobile/v1/portfolio")
    }

    func fetchInbox() async throws -> MobileInboxEnvelope {
        try await request(path: "mobile/v1/inbox")
    }

    func recordDecision(
        dealID: String,
        action: String,
        rationale: String?,
        reasonCodes: [String] = [],
        deferredUntil: Date? = nil,
        idempotencyKey: String = UUID().uuidString
    ) async throws -> MobileAPIProcurement {
        let body = MobileDecisionBody(
            action: action,
            rationale: rationale,
            reasonCodes: reasonCodes,
            deferredUntil: deferredUntil,
            idempotencyKey: idempotencyKey,
            actorRef: "tender-agent-ios"
        )
        return try await request(
            path: "mobile/v1/procurements/\(dealID)/decision",
            method: "POST",
            body: body
        )
    }

    private func request<Response: Decodable>(
        path: String,
        method: String = "GET"
    ) async throws -> Response {
        let request = try makeRequest(path: path, method: method, bodyData: nil)
        return try await perform(request)
    }

    private func request<Response: Decodable, Body: Encodable>(
        path: String,
        method: String,
        body: Body
    ) async throws -> Response {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(body)
        let request = try makeRequest(path: path, method: method, bodyData: data)
        return try await perform(request)
    }

    private func makeRequest(
        path: String,
        method: String,
        bodyData: Data?
    ) throws -> URLRequest {
        let url = configuration.baseURL.appending(path: path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 20
        request.httpBody = bodyData
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if bodyData != nil {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        let credentials = "\(configuration.username):\(configuration.password)"
        let encoded = Data(credentials.utf8).base64EncodedString()
        request.setValue("Basic \(encoded)", forHTTPHeaderField: "Authorization")
        return request
    }

    private func perform<Response: Decodable>(_ request: URLRequest) async throws -> Response {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw TenderAgentAPIError.invalidResponse
        }
        guard 200..<300 ~= http.statusCode else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw TenderAgentAPIError.httpStatus(http.statusCode, body)
        }

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(Response.self, from: data)
    }
}

private struct MobileDecisionBody: Encodable {
    let action: String
    let rationale: String?
    let reasonCodes: [String]
    let deferredUntil: Date?
    let idempotencyKey: String
    let actorRef: String
}

struct MobilePortfolioEnvelope: Decodable {
    let summary: MobilePortfolioSummary
    let items: [MobileAPIProcurement]
}

struct MobileInboxEnvelope: Decodable {
    let summary: MobileInboxSummary
    let items: [MobileAPIProcurement]
}

struct MobilePortfolioSummary: Decodable {
    let totalConsidered: Int
    let go: Int
    let noGo: Int
    let needsReview: Int
    let undecided: Int
    let submitted: Int
    let won: Int
    let lost: Int
    let rejected: Int
    let cancelled: Int
    let submissionRate: Double
    let winRate: Double
}

struct MobileInboxSummary: Decodable {
    let totalPortfolio: Int
    let needsAttention: Int
    let deferred: Int
    let submitted: Int
    let won: Int
    let lost: Int
    let cancelled: Int
}

struct MobileAPIProcurement: Decodable {
    let dealId: String
    let procurementNumber: String?
    let title: String
    let customerName: String?
    let sourceUrl: String?
    let nmckRub: Double?
    let deadlineAt: Date?
    let recommendation: String
    let recommendationRationale: String?
    let recommendationReasonCodes: [String]
    let humanDecision: String
    let humanRationale: String?
    let humanReasonCodes: [String]
    let deferredUntil: Date?
    let needsAttention: Bool
    let submitted: Bool
    let submittedAt: Date?
    let outcome: String?
    let outcomeRationale: String?
    let outcomeAt: Date?
    let postmortemRootCause: String?
    let currentStatus: String
    let updatedAt: Date
}
