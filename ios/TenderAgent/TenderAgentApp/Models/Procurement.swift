import Foundation

enum AgentRecommendation: String, Codable, CaseIterable {
    case go = "GO"
    case noGo = "NO GO"
    case review = "ПРОВЕРИТЬ"
}

enum HumanDecision: String, Codable, CaseIterable {
    case pending = "Ждёт решения"
    case go = "GO"
    case noGo = "NO GO"
    case deferred = "Отложено"
}

enum LifecycleState: String, Codable {
    case new = "Новая"
    case analysisReady = "Отчёт готов"
    case submitted = "Подались"
    case outcome = "Есть результат"
}

struct Procurement: Identifiable, Equatable {
    let id: String
    let registryNumber: String
    let title: String
    let customer: String
    let nmckRub: Int
    let deadline: Date
    let sourceURL: URL?
    let recommendation: AgentRecommendation
    let confidence: Double
    let goReasons: [String]
    let noGoReasons: [String]
    let blockers: [String]
    let unknowns: [String]
    let risks: [String]
    let summary: String
    let lifecycle: LifecycleState
    var decision: HumanDecision
    var decisionComment: String?
    var deferredUntil: Date?
}

extension Procurement {
    var daysUntilDeadline: Int {
        max(0, Calendar.current.dateComponents([.day], from: .now, to: deadline).day ?? 0)
    }

    var formattedNMCK: String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = " "
        formatter.maximumFractionDigits = 0
        let value = formatter.string(from: NSNumber(value: nmckRub)) ?? "\(nmckRub)"
        return "\(value) ₽"
    }
}
