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

enum PortfolioDecision: String, Codable, CaseIterable {
    case go = "GO"
    case noGo = "NO_GO"
    case needsReview = "NEEDS_REVIEW"
    case undecided = "UNDECIDED"

    var displayTitle: String {
        switch self {
        case .go: "GO"
        case .noGo: "NO GO"
        case .needsReview: "Проверить"
        case .undecided: "Не решено"
        }
    }
}

enum LifecycleState: String, Codable {
    case new = "Новая"
    case analysisReady = "Отчёт готов"
    case submitted = "Подались"
    case outcome = "Есть результат"
}

enum PortfolioFilter: String, CaseIterable, Identifiable {
    case all
    case attention
    case go
    case noGo
    case submitted
    case won
    case notWon
    case cancelled
    case awaitingOutcome

    var id: String { rawValue }

    var title: String {
        switch self {
        case .all: "Все"
        case .attention: "Решить"
        case .go: "GO"
        case .noGo: "NO GO"
        case .submitted: "Подались"
        case .won: "Победы"
        case .notWon: "Не выиграли"
        case .cancelled: "Отменены"
        case .awaitingOutcome: "Ждём итог"
        }
    }

    func matches(_ procurement: Procurement) -> Bool {
        switch self {
        case .all:
            true
        case .attention:
            procurement.needsAttention
        case .go:
            procurement.portfolioDecision == .go
        case .noGo:
            procurement.portfolioDecision == .noGo
        case .submitted:
            procurement.submitted
        case .won:
            procurement.outcomeCode == "WON"
        case .notWon:
            procurement.outcomeCode == "LOST" || procurement.outcomeCode == "REJECTED"
        case .cancelled:
            procurement.outcomeCode == "CANCELLED"
        case .awaitingOutcome:
            procurement.submitted && procurement.outcomeCode == nil
        }
    }
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
    let confidenceLabel: String?
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

    var portfolioDecision: PortfolioDecision = .undecided
    var portfolioDecisionSource: String? = nil
    var portfolioDecisionAt: Date? = nil
    var submitted: Bool = false
    var submittedAt: Date? = nil
    var outcomeCode: String? = nil
    var outcomeRationale: String? = nil
    var outcomeAt: Date? = nil
    var postmortemRootCause: String? = nil
    var backendStatus: String = ""
    var updatedAt: Date = .distantPast
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

    var outcomeLabel: String? {
        switch outcomeCode {
        case "WON": "Выиграли"
        case "LOST": "Проиграли"
        case "REJECTED": "Заявка отклонена"
        case "CANCELLED": "Закупка отменена"
        case "NO_RESULT": "Результата нет"
        case let code?: code
        case nil: nil
        }
    }

    var portfolioStateLabel: String {
        if let outcomeLabel {
            return outcomeLabel
        }
        if submitted {
            return "Подались"
        }
        return portfolioDecision.displayTitle
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

        let portfolioDecision = PortfolioDecision(rawValue: item.portfolioDecision) ?? .undecided
        let normalizedOutcome = item.outcome?.uppercased()

        let lifecycle: LifecycleState
        if normalizedOutcome != nil {
            lifecycle = .outcome
        } else if item.submitted {
            lifecycle = .submitted
        } else {
            lifecycle = .analysisReady
        }

        let rationale =
            item.recommendationRationale
            ?? item.humanRationale
            ?? "Анализ доступен в Tender Agent."
        let reasons = item.recommendationReasons.isEmpty
            ? item.recommendationReasonCodes
            : item.recommendationReasons
        let goReasons = recommendation == .go ? reasons : []
        let noGoReasons = recommendation == .noGo ? reasons : []

        return Procurement(
            id: item.dealId,
            registryNumber: item.procurementNumber ?? item.dealId,
            title: item.title,
            customer: item.customerName ?? "Заказчик не указан",
            nmckRub: item.nmckRub,
            deadline: item.deadlineAt,
            sourceURL: item.sourceUrl.flatMap(URL.init(string:)),
            recommendation: recommendation,
            confidenceLabel: item.recommendationConfidence,
            goReasons: goReasons,
            noGoReasons: noGoReasons,
            blockers: item.recommendationBlockers,
            unknowns: item.recommendationUnknowns,
            risks: [],
            summary: rationale,
            lifecycle: lifecycle,
            needsAttention: item.needsAttention,
            decision: decision,
            decisionComment: item.humanRationale,
            deferredUntil: item.deferredUntil,
            portfolioDecision: portfolioDecision,
            portfolioDecisionSource: item.portfolioDecisionSource,
            portfolioDecisionAt: item.portfolioDecisionAt,
            submitted: item.submitted,
            submittedAt: item.submittedAt,
            outcomeCode: normalizedOutcome,
            outcomeRationale: item.outcomeRationale,
            outcomeAt: item.outcomeAt,
            postmortemRootCause: item.postmortemRootCause,
            backendStatus: item.currentStatus,
            updatedAt: item.updatedAt
        )
    }
}
