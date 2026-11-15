import XCTest
@testable import TenderAgent

@MainActor
final class AppStoreTests: XCTestCase {
    func testDailyDigestDistinguishesEmptyPartialPendingAndLegacy() throws {
        let decoder = TenderAgentJSON.makeDecoder()
        func digest(_ json: String) throws -> MobileDailyDigest {
            try decoder.decode(MobileDailyDigest.self, from: Data(json.utf8))
        }
        let empty = try digest(#"{"run_id":"DTR-test","run_status":"COMPLETED","discovery_incomplete":false,"counts":{"discovered":0}}"#)
        XCTAssertEqual(empty.statusLabel, "Новых закупок нет")
        XCTAssertFalse(empty.needsReview)
        let partial = try digest(#"{"run_id":"DTR-test","run_status":"WAITING_HUMAN","discovery_incomplete":true,"counts":{"discovered":3}}"#)
        XCTAssertEqual(partial.statusLabel, "Поиск неполный")
        XCTAssertTrue(partial.needsReview)
        let pending = try digest(#"{"run_id":"DTR-test","run_status":"PENDING","current_stage":"DISCOVER","discovery_incomplete":null}"#)
        XCTAssertEqual(pending.statusLabel, "Ожидает запуска")
        XCTAssertNil(pending.discoveryIncomplete)
        let legacy = try digest(#"{"run_id":"DTR-old","counts":{"discovered":0}}"#)
        XCTAssertEqual(legacy.statusLabel, "Состояние требует уточнения")
        XCTAssertNil(legacy.discoveryIncomplete)
        let oldCompleted = try digest(#"{"run_id":"DTR-old","run_status":"COMPLETED","counts":{"discovered":0}}"#)
        XCTAssertEqual(oldCompleted.statusLabel, "Полнота поиска неизвестна")
        XCTAssertEqual(try digest(#"{"run_id":null}"#).statusLabel, "Нет данных о последнем запуске")
    }

    func testCompanyProjectionAndIdentityBoundary() throws {
        let decoder = TenderAgentJSON.makeDecoder()
        let a = try decoder.decode(CompanyIdentity.self, from: Data(#"{"tenant_id":"a","customer_id":"a","member_id":"m","company_name":"Company A","role":"owner","legal_accepted":true}"#.utf8))
        let b = try decoder.decode(CompanyIdentity.self, from: Data(#"{"tenant_id":"b","customer_id":"b","member_id":"m","company_name":"Company B","role":"owner","legal_accepted":true}"#.utf8))
        let page = try decoder.decode(CompanyPortfolioPage.self, from: Data(#"{"customer_id":"a","items":[{"case_id":"case-a","registry_number":"0123456789012345678","source_verified":false,"revision":0,"decision":null}],"has_more":false}"#.utf8))
        XCTAssertTrue(a.matchesAccount(a))
        XCTAssertFalse(a.matchesAccount(b))
        XCTAssertTrue(page.matchesCompany(a))
        XCTAssertFalse(page.matchesCompany(b))
        XCTAssertEqual(page.items.map(\.caseId), ["case-a"])
        XCTAssertFalse(page.items[0].sourceVerified)
        XCTAssertThrowsError(try CompanyAPIClient.validatedOrigin("http://example.invalid"))
        XCTAssertThrowsError(try CompanyAPIClient.validatedOrigin("https://example.invalid/path"))
        XCTAssertThrowsError(try CompanyAPIClient.validatedOrigin("https://user@example.invalid"))
        XCTAssertEqual(try CompanyAPIClient.validatedOrigin("https://EXAMPLE.invalid:443/").absoluteString, "https://example.invalid")
    }

    func testCompanyDecisionAttemptIdentityAndRevision() throws {
        let now = Date(timeIntervalSince1970: 1800000000)
        let draft = try CompanyDecisionDraft(action: "GO", rationale: "  Проверено  ", deferredUntil: nil, expectedRevision: 2, now: now)
        let first = CompanyDecisionAttempt.prepare(previous: nil, accountID: "account-A", caseID: "case-A", draft: draft)
        XCTAssertEqual(first.draft.rationale, "Проверено")
        XCTAssertEqual(CompanyDecisionAttempt.prepare(previous: first, accountID: "account-A", caseID: "case-A", draft: draft).key, first.key)
        XCTAssertNotEqual(CompanyDecisionAttempt.prepare(previous: first, accountID: "account-B", caseID: "case-A", draft: draft).key, first.key)
        let later = try CompanyDecisionDraft(action: "GO", rationale: "Проверено", deferredUntil: nil, expectedRevision: 3, now: now)
        XCTAssertNotEqual(CompanyDecisionAttempt.prepare(previous: first, accountID: "account-A", caseID: "case-A", draft: later).key, first.key)
        let response = try TenderAgentJSON.makeDecoder().decode(CompanyDecision.self, from: Data(#"{"revision":3,"action":"GO","rationale":"Проверено","deferred_until":null,"decided_at":"2026-11-15T00:00:00Z","decided_by_member_id":"member-A"}"#.utf8))
        XCTAssertTrue(first.accepts(response, memberID: "member-A"))
        XCTAssertFalse(first.accepts(response, memberID: "member-B"))
        XCTAssertFalse(CompanyDecisionAttempt.prepare(previous: first, accountID: "account-A", caseID: "case-A", draft: later).accepts(response, memberID: "member-A"))
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        let body = try XCTUnwrap(JSONSerialization.jsonObject(with: encoder.encode(first.payload)) as? [String: Any])
        XCTAssertEqual(body["expected_revision"] as? Int, 2)
        XCTAssertEqual(body["idempotency_key"] as? String, first.key)
        XCTAssertEqual(body["action"] as? String, "GO")
        XCTAssertThrowsError(try CompanyDecisionDraft(action: "DEFER", rationale: "Причина", deferredUntil: now, expectedRevision: 0, now: now))
        XCTAssertThrowsError(try CompanyDecisionDraft(action: "GO", rationale: " ", deferredUntil: nil, expectedRevision: 0, now: now))
        let deferDraft = try CompanyDecisionDraft(action: "DEFER", rationale: "Причина", deferredUntil: now.addingTimeInterval(86400.7), expectedRevision: 0, now: now)
        XCTAssertEqual(deferDraft.deferredUntil, now.addingTimeInterval(86400))
    }

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
