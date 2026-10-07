import XCTest
@testable import TenderAgent

@MainActor
final class AppStoreTests: XCTestCase {
    func testMockModeIsExplicitWithoutBackend() {
        let store = AppStore(procurements: [makeProcurement()], apiClient: nil)

        XCTAssertTrue(store.isMockData)
        XCTAssertFalse(store.isLive)
        XCTAssertEqual(store.connectionLabel, "Не подключено")
        XCTAssertFalse(store.canSubmitDecisions)
    }

    func testAPIProjectionPreservesRecommendationEvidence() {
        let item = MobileAPIProcurement(
            dealId: "DL-1",
            procurementNumber: "0123456789012345678",
            title: "Тестовая закупка",
            customerName: "Заказчик",
            sourceUrl: "https://zakupki.gov.ru",
            nmckRub: 1_500_000,
            deadlineAt: Date(timeIntervalSince1970: 1_800_000_000),
            recommendation: "NEEDS_REVIEW",
            recommendationRationale: "Нужно проверить блокеры.",
            recommendationReasonCodes: ["DTR"],
            recommendationConfidence: "MEDIUM",
            recommendationReasons: ["Технически выполнимо"],
            recommendationBlockers: ["Нужна проверка лицензии"],
            recommendationUnknowns: ["Неясен объём интеграции"],
            analysisRunId: "analysis-1",
            analysisReportPath: "/reports/analysis-1",
            humanDecision: "PENDING",
            humanRationale: nil,
            humanReasonCodes: [],
            deferredUntil: nil,
            needsAttention: true,
            portfolioDecision: "NEEDS_REVIEW",
            portfolioDecisionSource: "AGENT_SCREENING",
            portfolioDecisionAt: Date(timeIntervalSince1970: 1_800_000_050),
            submitted: false,
            submittedAt: nil,
            outcome: nil,
            outcomeRationale: nil,
            outcomeAt: nil,
            postmortemRootCause: nil,
            currentStatus: "analysis_ready",
            updatedAt: Date(timeIntervalSince1970: 1_800_000_100)
        )

        let procurement = Procurement.fromAPI(item)

        XCTAssertEqual(procurement.recommendation, .review)
        XCTAssertEqual(procurement.confidenceLabel, "MEDIUM")
        XCTAssertEqual(procurement.blockers, ["Нужна проверка лицензии"])
        XCTAssertEqual(procurement.unknowns, ["Неясен объём интеграции"])
        XCTAssertEqual(procurement.summary, "Нужно проверить блокеры.")
        XCTAssertTrue(procurement.needsAttention)
        XCTAssertEqual(procurement.portfolioDecision, .needsReview)
        XCTAssertEqual(procurement.portfolioDecisionSource, "AGENT_SCREENING")
    }

    func testPortfolioSummaryDecodesCanonicalMetrics() throws {
        let json = #"""
        {
          "total_considered": 10,
          "go": 6,
          "no_go": 2,
          "needs_review": 1,
          "undecided": 1,
          "submitted": 4,
          "won": 2,
          "lost": 1,
          "rejected": 1,
          "cancelled": 1,
          "submission_rate": 0.6667,
          "win_rate": 0.5,
          "no_go_reason_counts": {"ECONOMICS": 2}
        }
        """#.data(using: .utf8)!

        let summary = try TenderAgentJSON.makeDecoder().decode(
            MobilePortfolioSummary.self,
            from: json
        )

        XCTAssertEqual(summary.totalConsidered, 10)
        XCTAssertEqual(summary.submitted, 4)
        XCTAssertEqual(summary.won, 2)
        XCTAssertEqual(summary.rejected, 1)
        XCTAssertEqual(summary.submissionRate, 0.6667, accuracy: 0.0001)
        XCTAssertEqual(summary.winRate, 0.5, accuracy: 0.0001)
    }

    func testPortfolioFiltersUseCanonicalFacts() {
        let awaiting = makeProcurement(
            id: "WAIT",
            portfolioDecision: .go,
            submitted: true,
            outcomeCode: nil,
            needsAttention: false
        )
        let won = makeProcurement(
            id: "WON",
            portfolioDecision: .go,
            submitted: true,
            outcomeCode: "WON",
            needsAttention: false
        )
        let rejected = makeProcurement(
            id: "REJECTED",
            portfolioDecision: .go,
            submitted: true,
            outcomeCode: "REJECTED",
            needsAttention: false
        )
        let noGo = makeProcurement(
            id: "NO-GO",
            portfolioDecision: .noGo,
            submitted: false,
            outcomeCode: nil,
            needsAttention: false
        )

        XCTAssertTrue(PortfolioFilter.awaitingOutcome.matches(awaiting))
        XCTAssertFalse(PortfolioFilter.awaitingOutcome.matches(won))
        XCTAssertTrue(PortfolioFilter.won.matches(won))
        XCTAssertTrue(PortfolioFilter.notWon.matches(rejected))
        XCTAssertTrue(PortfolioFilter.noGo.matches(noGo))
        XCTAssertFalse(PortfolioFilter.submitted.matches(noGo))
    }

    func testDecisionActionWireValuesMatchBackendContract() {
        XCTAssertEqual(MobileDecisionAction.go.rawValue, "GO")
        XCTAssertEqual(MobileDecisionAction.noGo.rawValue, "NO_GO")
        XCTAssertEqual(MobileDecisionAction.deferDecision.rawValue, "DEFER")
    }

    func testDecisionPayloadEncodesBackendFieldNames() throws {
        let payload = MobileDecisionRequest(
            action: .deferDecision,
            rationale: "Проверить завтра",
            reasonCodes: [],
            deferredUntil: Date(timeIntervalSince1970: 1_800_000_000),
            idempotencyKey: "ios-test-idempotency"
        )
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(payload)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(json["action"] as? String, "DEFER")
        XCTAssertEqual(json["rationale"] as? String, "Проверить завтра")
        XCTAssertEqual(json["idempotency_key"] as? String, "ios-test-idempotency")
        XCTAssertNotNil(json["deferred_until"])
    }

    func testOfflineDecisionDoesNotMutateMockState() async {
        let original = makeProcurement()
        let store = AppStore(procurements: [original], apiClient: nil)

        let saved = await store.submitDecision(
            dealID: original.id,
            action: .go,
            rationale: "Не должно сохраниться"
        )

        XCTAssertFalse(saved)
        XCTAssertEqual(store.procurement(id: original.id)?.decision, .pending)
        XCTAssertNotNil(store.decisionError)
        XCTAssertNil(store.decisionMessage)
    }

    func testDeepLinkParsesProcurementAndDigest() throws {
        let procurementURL = try XCTUnwrap(
            URL(string: "tenderagent://procurement/DL-MOB-123")
        )
        XCTAssertEqual(
            TenderAgentDeepLink(url: procurementURL),
            .procurement("DL-MOB-123")
        )

        let digestURL = try XCTUnwrap(URL(string: "tenderagent://digest"))
        XCTAssertEqual(TenderAgentDeepLink(url: digestURL), .digest)

        XCTAssertNil(
            TenderAgentDeepLink(
                url: try XCTUnwrap(URL(string: "https://example.com/procurement/DL-MOB-123"))
            )
        )
    }

    func testPushPayloadUserInfoRoutesToProcurement() {
        let parsed = TenderAgentDeepLink(
            userInfo: [
                "event_type": "REPORT_READY",
                "deep_link": "tenderagent://procurement/DL-MOB-PUSH",
                "deal_id": "DL-MOB-PUSH"
            ]
        )
        XCTAssertEqual(parsed, .procurement("DL-MOB-PUSH"))
    }

    func testPushRegistrationPayloadEncodesBackendFieldNames() throws {
        let payload = MobileDeviceRegistrationRequest(
            apnsToken: "ab" + String(repeating: "12", count: 31),
            environment: .sandbox,
            deviceName: "iPhone Test",
            appVersion: "0.7.0"
        )
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        let data = try encoder.encode(payload)
        let json = try XCTUnwrap(
            JSONSerialization.jsonObject(with: data) as? [String: Any]
        )

        XCTAssertEqual(json["environment"] as? String, "sandbox")
        XCTAssertEqual(json["device_name"] as? String, "iPhone Test")
        XCTAssertEqual(json["app_version"] as? String, "0.7.0")
        XCTAssertNotNil(json["apns_token"])
    }

    func testOfflinePushTokenDoesNotMutateProcurementState() async {
        let original = makeProcurement()
        let store = AppStore(procurements: [original], apiClient: nil)

        await store.receiveAPNSToken(String(repeating: "ab", count: 32))

        XCTAssertEqual(store.procurement(id: original.id)?.decision, .pending)
        XCTAssertEqual(store.pushStatusLabel, "APNs готов — подключите backend")
        XCTAssertNil(store.pushRegistrationError)
    }

    private func makeProcurement(
        id: String = "TEST-1",
        portfolioDecision: PortfolioDecision = .undecided,
        submitted: Bool = false,
        outcomeCode: String? = nil,
        needsAttention: Bool = true
    ) -> Procurement {
        Procurement(
            id: id,
            registryNumber: "0000000000000000001",
            title: "Тестовая закупка",
            customer: "Тестовый заказчик",
            nmckRub: 100_000.0,
            deadline: .now.addingTimeInterval(86_400),
            sourceURL: nil,
            recommendation: .go,
            confidenceLabel: "HIGH",
            goReasons: ["Подходит"],
            noGoReasons: [],
            blockers: [],
            unknowns: [],
            risks: [],
            summary: "Тест.",
            lifecycle: outcomeCode == nil ? (submitted ? .submitted : .analysisReady) : .outcome,
            needsAttention: needsAttention,
            decision: .pending,
            portfolioDecision: portfolioDecision,
            submitted: submitted,
            outcomeCode: outcomeCode,
            updatedAt: .now
        )
    }
}
