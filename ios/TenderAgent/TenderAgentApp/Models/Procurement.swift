import Foundation

enum AgentRecommendation: String, Codable, CaseIterable {
    case go = "GO"
    case noGo = "NO GO"
    case review = "ПРОВЕРИТЬ"
    case undecided = "НЕ РЕШЕНО"
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
    let nmckRub: Double?
    let deadline: Date?
    let sourceURL: URL?
    let recommendation: AgentRecommendation
    let confidence: Double?
    let goReasons: [String]
    let noGoReasons: [String]
    let blockers: [String]
    let unknowns: [String]
    let risks: [String]
    let summary: String
    let lifecycle: LifecycleState
    var needsAttention: Bool
    var decision: HumanDecision
    var decisionComment: String?
    var deferredUntil: Date?
}

extension Procurement {
    var daysUntilDeadline: Int? {
        guard let deadline else { return nil }
        return max(0, Calendar.current.dateComponents([.day], from: .now, to: deadline).day ?? 0)
    }

    var formattedNMCK: String {
        guard let nmckRub else { return "НМЦК не загружена" }
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = " "
        formatter.maximumFractionDigits = 0
        let value = formatter.string(from: NSNumber(value: nmckRub)) ?? "\(Int(nmckRub))"
        return "\(value) ₽"
    }

    var deadlineText: String {
        guard let daysUntilDeadline else { return "срок не загружен" }
        return "\(daysUntilDeadline) дн."
    }

    static func fromAPI(_ item: MobileAPIProcurement) -> Procurement {
        let recommendation: AgentRecommendation
        switch item.recommendation {
        case "GO": recommendation = .go
        case "NO_GO": recommendation = .noGo
        case "NEEDS_REVIEW": recommendation = .review
        default: recommendation = .undecided
        }

        let decision: HumanDecision
        switch item.humanDecision {
        case "GO": decision = .go
        case "NO_GO": decision = .noGo
        case "DEFER": decision = .deferred
        default: decision = .pending
        }

        let lifecycle: LifecycleState
        if item.outcome != nil {
            lifecycle = .outcome
        } else if item.submitted {
            lifecycle = .submitted
        } else {
            lifecycle = .analysisReady
        }

        let rationale = item.recommendationRationale ?? item.humanRationale ?? "Анализ доступен в Tender Agent."
        let codes = item.recommendationReasonCodes
        let goReasons = recommendation == .go ? codes : []
        let noGoReasons = recommendation == .noGo ? codes : []

        return Procurement(
            id: item.dealId,
            registryNumber: item.procurementNumber ?? item.dealId,
            title: item.title,
            customer: item.customerName ?? "Заказчик не указан",
            nmckRub: item.nmckRub,
            deadline: item.deadlineAt,
            sourceURL: item.sourceUrl.flatMap(URL.init(string:)),
            recommendation: recommendation,
            confidence: nil,
            goReasons: goReasons,
            noGoReasons: noGoReasons,
            blockers: [],
            unknowns: [],
            risks: [],
            summary: rationale,
            lifecycle: lifecycle,
            needsAttention: item.needsAttention,
            decision: decision,
            decisionComment: item.humanRationale,
            deferredUntil: item.deferredUntil
        )
    }
}
