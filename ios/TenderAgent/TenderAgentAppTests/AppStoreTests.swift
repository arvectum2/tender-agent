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

    private func makeProcurement() -> Procurement {
        Procurement(
            id: "TEST-1",
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
            lifecycle: .analysisReady,
            needsAttention: true,
            decision: .pending
        )
    }
}
