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

enum MobileDecisionAction: String, Codable, CaseIterable, Identifiable {
    case go = "GO"
    case noGo = "NO_GO"
    case deferDecision = "DEFER"

    var id: String { rawValue }

    var displayTitle: String {
        switch self {
        case .go: "GO"
        case .noGo: "NO GO"
        case .deferDecision: "Отложить"
        }
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
            switch code {
            case 401:
                return "Сессия iPhone не авторизована. Переподключите Tender Agent в настройках."
            case 403:
                return "Мобильное действие запрещено для этого устройства."
            case 404:
                return "Закупка не найдена в Tender Agent."
            case 422:
                return "Backend отклонил параметры решения. Проверьте действие и дату отсрочки."
            default:
                let suffix = body.isEmpty ? "" : ": \(body)"
                return "Backend вернул HTTP \(code)\(suffix)"
            }
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

    func fetchProcurement(dealID: String) async throws -> MobileAPIProcurement {
        try await request(path: "mobile/v1/procurements/\(dealID)")
    }

    func registerDevice(
        apnsToken: String,
        environment: MobileAPNsEnvironment = .current,
        deviceName: String,
        appVersion: String?
    ) async throws -> MobileDeviceRegistrationResponse {
        let payload = MobileDeviceRegistrationRequest(
            apnsToken: apnsToken,
            environment: environment,
            deviceName: deviceName,
            appVersion: appVersion
        )
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase

        var request = authorizedRequest(path: "mobile/v1/devices", method: "POST")
        request.httpBody = try encoder.encode(payload)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await perform(request)
    }

    func revokeDevice(deviceID: String) async throws {
        let request = authorizedRequest(
            path: "mobile/v1/devices/\(deviceID)",
            method: "DELETE"
        )
        try await performNoContent(request)
    }

    func recordDecision(
        dealID: String,
        action: MobileDecisionAction,
        rationale: String?,
        deferredUntil: Date?,
        idempotencyKey: String = UUID().uuidString
    ) async throws -> MobileAPIProcurement {
        let payload = MobileDecisionRequest(
            action: action,
            rationale: rationale,
            reasonCodes: [],
            deferredUntil: deferredUntil,
            idempotencyKey: idempotencyKey
        )
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601

        var request = authorizedRequest(
            path: "mobile/v1/procurements/\(dealID)/decision",
            method: "POST"
        )
        request.httpBody = try encoder.encode(payload)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await perform(request)
    }

    private func request<Response: Decodable>(path: String) async throws -> Response {
        try await perform(authorizedRequest(path: path, method: "GET"))
    }

    private func authorizedRequest(path: String, method: String) -> URLRequest {
        let url = configuration.baseURL.appending(path: path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue(
            "Bearer \(configuration.accessToken)",
            forHTTPHeaderField: "Authorization"
        )
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
        return try TenderAgentJSON.makeDecoder().decode(Response.self, from: data)
    }

    private func performNoContent(_ request: URLRequest) async throws {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw TenderAgentAPIError.invalidResponse
        }
        guard 200..<300 ~= http.statusCode else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw TenderAgentAPIError.httpStatus(http.statusCode, body)
        }
    }
}

private struct MobilePairRequest: Encodable {
    let pairingCode: String
    let deviceId: String
    let deviceName: String
}

enum MobileAPNsEnvironment: String, Codable {
    case sandbox
    case production

    static var current: MobileAPNsEnvironment {
#if DEBUG
        .sandbox
#else
        .production
#endif
    }
}

struct MobileDeviceRegistrationRequest: Encodable {
    let apnsToken: String
    let environment: MobileAPNsEnvironment
    let deviceName: String
    let appVersion: String?
}

struct MobileDeviceRegistrationResponse: Decodable {
    let deviceId: String
    let environment: MobileAPNsEnvironment
    let deviceName: String?
    let appVersion: String?
    let enabled: Bool
    let registeredAt: Date
    let updatedAt: Date
}

struct MobileDecisionRequest: Encodable {
    let action: MobileDecisionAction
    let rationale: String?
    let reasonCodes: [String]
    let deferredUntil: Date?
    let idempotencyKey: String
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
