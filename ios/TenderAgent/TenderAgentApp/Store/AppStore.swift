import Combine
import Foundation

@MainActor
final class AppStore: ObservableObject {
    @Published private(set) var procurements: [Procurement]

    init(procurements: [Procurement] = MockData.procurements) {
        self.procurements = procurements
    }

    var decisionNeeded: [Procurement] {
        procurements.filter { $0.decision == .pending || $0.decision == .deferred }
    }

    var submittedCount: Int {
        procurements.filter { $0.lifecycle == .submitted || $0.lifecycle == .outcome }.count
    }

    var goCount: Int {
        procurements.filter { $0.decision == .go }.count
    }

    var noGoCount: Int {
        procurements.filter { $0.decision == .noGo }.count
    }

    func procurement(id: String) -> Procurement? {
        procurements.first { $0.id == id }
    }

    func setDecision(
        _ decision: HumanDecision,
        for id: String,
        comment: String? = nil,
        deferredUntil: Date? = nil
    ) {
        guard let index = procurements.firstIndex(where: { $0.id == id }) else { return }

        procurements[index].decision = decision
        procurements[index].decisionComment = comment
        procurements[index].deferredUntil = decision == .deferred ? deferredUntil : nil
    }
}
