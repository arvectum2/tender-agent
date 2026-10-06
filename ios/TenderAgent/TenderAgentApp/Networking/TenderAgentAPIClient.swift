import Foundation

enum TenderAgentJSON {
    static func makeDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let value = try container.decode(String.self)

            let fractional = ISO8601DateFormatter()
            fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = fractional.date(from: value) {
                return date
            }

            let standard = ISO8601DateFormatter()
            standard.formatOptions = [.withInternetDateTime]
            if let date = standard.date(from: value) {
                return date
            }

            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Unsupported ISO-8601 date: \(value)"
            )
        }
        return decoder
    }
}

struct TenderAgentAPIConfiguration {
    let baseURL: URL
    let accessToken: String
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

struct TenderAgentPairingClient {
    let baseURL: URL
    let session: URLSession

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func pair(
        code: String,
        deviceID: String,
        deviceName: String
    ) async throws -> MobilePairResponse {
        let body = MobilePairRequest(
            pairingCode: code,
            deviceId: deviceID,
            deviceName: deviceName
        )
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        let data = try encoder.encode(body)

        var request = URLRequest(url: baseURL.appending(path: "mobile/v1/pair"))
        request.httpMethod = "POST"
        request.timeoutInterval = 20
        request.httpBody = data
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        return try await perform(request)
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
        return try TenderAgentJSON.makeDecoder().decode(Response.self, from: data)
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

    private func request<Response: Decodable>(path: String) async throws -> Response {
        let url = configuration.baseURL.appending(path: path)
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue(
            "Bearer \(configuration.accessToken)",
            forHTTPHeaderField: "Authorization"
        )

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw TenderAgentAPIError.invalidResponse
        }
        guard 200..<300 ~= http.statusCode else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw TenderAgentAPIError.httpStatus(http.statusCode, body)
        }
        return try TenderAgentJSON.makeDecoder().decode(Response.self, from: data)
    }
}

private struct MobilePairRequest: Encodable {
    let pairingCode: String
    let deviceId: String
    let deviceName: String
}

struct MobilePairResponse: Decodable {
    let accessToken: String
    let tokenType: String
    let expiresAt: Date
    let deviceId: String
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
    let recommendationConfidence: String?
    let recommendationReasons: [String]
    let recommendationBlockers: [String]
    let recommendationUnknowns: [String]
    let analysisRunId: String?
    let analysisReportPath: String?

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
