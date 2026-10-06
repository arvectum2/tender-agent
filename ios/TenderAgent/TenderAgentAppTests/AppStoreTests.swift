import XCTest
@testable import TenderAgent

@MainActor
final class AppStoreTests: XCTestCase {
    func testGoDecisionUpdatesProcurement() {
        let procurement = makeProcurement()
        let store = AppStore(procurements: [procurement])

        store.setDecision(.go, for: procurement.id)

        XCTAssertEqual(store.procurement(id: procurement.id)?.decision, .go)
        XCTAssertEqual(store.goCount, 1)
        XCTAssertEqual(store.decisionNeeded.count, 0)
    }

    func testDeferredDecisionTracksReturnDate() {
        let procurement = makeProcurement()
        let store = AppStore(procurements: [procurement])
        let returnDate = Date.now.addingTimeInterval(3_600)

        store.setDecision(.deferred, for: procurement.id, deferredUntil: returnDate)

        XCTAssertEqual(store.procurement(id: procurement.id)?.decision, .deferred)
        XCTAssertEqual(store.procurement(id: procurement.id)?.deferredUntil, returnDate)
        XCTAssertEqual(store.decisionNeeded.count, 0)
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
            confidence: 0.9,
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
