import Foundation
import CryptoKit

struct CompanyIdentity: Codable, Equatable, Sendable {
    let tenantId: String
    let customerId: String
    let memberId: String
    let companyName: String
    let role: String
    let legalAccepted: Bool

    func matchesAccount(_ expected: CompanyIdentity) -> Bool {
        tenantId == expected.tenantId && customerId == expected.customerId && memberId == expected.memberId
    }
}

struct CompanyConnection: Codable, Identifiable, Equatable, Sendable {
    let baseURL: URL
    let token: String
    let identity: CompanyIdentity

    var id: String { "\(baseURL.absoluteString)|\(identity.tenantId)|\(identity.memberId)" }
}

struct CompanyDecision: Codable, Sendable {
    let revision: Int
    let action: String
    let rationale: String
    let deferredUntil: Date?
    let decidedAt: Date
    let decidedByMemberId: String?
}

struct CompanyDecisionDraft: Equatable, Sendable {
    let action: String
    let rationale: String
    let deferredUntil: Date?
    let expectedRevision: Int

    init(action: String, rationale: String, deferredUntil: Date?, expectedRevision: Int, now: Date = Date()) throws {
        let text = rationale.trimmingCharacters(in: .whitespacesAndNewlines)
        guard ["GO", "NO_GO", "DEFER"].contains(action), !text.isEmpty,
              text.count <= 2000, expectedRevision >= 0 else { throw CompanyConnectionError.invalidDecision }
        let rounded = deferredUntil.map { Date(timeIntervalSince1970: floor($0.timeIntervalSince1970)) }
        if action == "DEFER" {
            guard let rounded, rounded > now else { throw CompanyConnectionError.invalidDecision }
        } else if rounded != nil { throw CompanyConnectionError.invalidDecision }
        self.action = action
        self.rationale = text
        self.deferredUntil = rounded
        self.expectedRevision = expectedRevision
    }
}

struct CompanyDecisionAttempt: Equatable, Sendable {
    let accountID: String
    let caseID: String
    let draft: CompanyDecisionDraft
    let key: String

    static func prepare(previous: Self?, accountID: String, caseID: String, draft: CompanyDecisionDraft) -> Self {
        if let previous, previous.accountID == accountID, previous.caseID == caseID, previous.draft == draft { return previous }
        return Self(accountID: accountID, caseID: caseID, draft: draft, key: UUID().uuidString)
    }

    struct Payload: Encodable {
        let action: String
        let rationale: String
        let deferredUntil: Date?
        let expectedRevision: Int
        let idempotencyKey: String
    }

    var payload: Payload {
        Payload(action: draft.action, rationale: draft.rationale, deferredUntil: draft.deferredUntil,
                expectedRevision: draft.expectedRevision, idempotencyKey: key)
    }

    func accepts(_ response: CompanyDecision, memberID: String) -> Bool {
        response.revision == draft.expectedRevision + 1 && response.action == draft.action &&
        response.rationale == draft.rationale && response.deferredUntil == draft.deferredUntil &&
        response.decidedByMemberId == memberID
    }
}

struct CompanyCase: Decodable, Identifiable, Sendable {
    let caseId: String
    let registryNumber: String?
    let sourcePlatform: String?
    let externalId: String?
    let sourceUrl: String?
    var displayReference: String { registryNumber ?? [sourcePlatform, externalId].compactMap { $0 }.joined(separator: ":") }
    var isCommercial: Bool { sourcePlatform != nil && sourcePlatform != "eis" }
    let sourceVerified: Bool
    let inboxState: String?
    let revision: Int
    let decision: CompanyDecision?
    var id: String { caseId }
}

struct CompanyPortfolioPage: Decodable, Sendable {
    let customerId: String
    let items: [CompanyCase]
    let hasMore: Bool

    func matchesCompany(_ identity: CompanyIdentity) -> Bool { customerId == identity.customerId }
}

enum CompanyInboxFilter: String, CaseIterable, Identifiable, Sendable {
    case attention, undecided, deferredDue = "deferred_due", deferredFuture = "deferred_future", go, noGo = "no_go", all
    var id: String { rawValue }
    var title: String {
        switch self {
        case .attention: "Требуют внимания"
        case .undecided: "Без решения"
        case .deferredDue: "Пора вернуться"
        case .deferredFuture: "Отложены"
        case .go: "GO"
        case .noGo: "NO GO"
        case .all: "Все закупки"
        }
    }
}

struct CompanyInboxSummary: Decodable, Sendable {
    let undecided: Int
    let deferredDue: Int
    let deferredFuture: Int
    let go: Int
    let noGo: Int
    let attention: Int
    let all: Int

    var valid: Bool {
        let counts = [undecided, deferredDue, deferredFuture, go, noGo, attention, all]
        return counts.allSatisfy { $0 >= 0 && $0 <= Int.max / 8 } &&
            attention == undecided + deferredDue && all == undecided + deferredDue + deferredFuture + go + noGo
    }
}

struct CompanyInboxPage: Decodable, Sendable {
    let customerId: String
    let asOf: Date
    let view: String
    let offset: Int
    let limit: Int
    let summary: CompanyInboxSummary
    let items: [CompanyCase]
    let hasMore: Bool
    let scope: String
    let marketCoverageComplete: Bool
    let liveDeadlineVerified: Bool
    let externalSubmissionAllowed: Bool

    func matches(_ identity: CompanyIdentity, filter: CompanyInboxFilter, offset expectedOffset: Int) -> Bool {
        guard customerId == identity.customerId, view == filter.rawValue, offset == expectedOffset,
              scope == "SAVED_COMPANY_REFERENCES_AND_HUMAN_DECISIONS", !externalSubmissionAllowed,
              !marketCoverageComplete, !liveDeadlineVerified, summary.valid, limit == 50,
              items.count <= limit, Set(items.map(\.caseId)).count == items.count,
              !hasMore || items.count == limit else { return false }
        return items.allSatisfy { item in
            let state: String
            if let action = item.decision {
                guard item.revision == action.revision else { return false }
                switch action.action {
                case "GO": state = "go"
                case "NO_GO": state = "no_go"
                case "DEFER":
                    guard let due = action.deferredUntil else { return false }
                    state = due <= asOf ? "deferred_due" : "deferred_future"
                default: return false
                }
            } else {
                guard item.revision == 0 else { return false }
                state = "undecided"
            }
            return item.inboxState == state && (filter == .all || (filter == .attention ? ["undecided", "deferred_due"].contains(state) : filter.rawValue == state))
        }
    }
}

enum CompanyLifecycleStage: String, Codable, CaseIterable, Identifiable, Sendable {
    case preparing = "PREPARING", blocked = "BLOCKED", ready = "READY", submitted = "SUBMITTED"
    case won = "WON", lost = "LOST", rejected = "REJECTED", withdrawn = "WITHDRAWN", cancelled = "CANCELLED"
    var id: String { rawValue }
    var isPreparation: Bool { [.preparing, .blocked, .ready].contains(self) }
    var isOutcome: Bool { !isPreparation && self != .submitted }
    var title: String {
        switch self {
        case .preparing: "Подготовка"
        case .blocked: "Заблокирована"
        case .ready: "Готовность подтверждена сотрудником"
        case .submitted: "Подача зарегистрирована"
        case .won: "Победа"
        case .lost: "Проигрыш"
        case .rejected: "Отклонена"
        case .withdrawn: "Отозвана"
        case .cancelled: "Отменена"
        }
    }
}

struct CompanyLifecycleDraft: Codable, Equatable, Sendable {
    let stage: CompanyLifecycleStage
    let rationale: String
    let sourceRef: String?
    let occurredAt: Date?
    let expectedRevision: Int
    let expectedDecisionRevision: Int
    let correctOutcome: Bool

    init(stage: CompanyLifecycleStage, rationale: String, sourceRef: String?, occurredAt: Date?, state: CompanyLifecycleState, now: Date = Date()) throws {
        let text = rationale.trimmingCharacters(in: .whitespacesAndNewlines)
        let ref = sourceRef?.trimmingCharacters(in: .whitespacesAndNewlines)
        let date = occurredAt.map { Date(timeIntervalSince1970: floor($0.timeIntervalSince1970)) }
        guard state.options.contains(stage), !text.isEmpty, text.count <= 2000 else { throw CompanyConnectionError.invalidLifecycle }
        if stage.isPreparation {
            guard ref == nil, date == nil else { throw CompanyConnectionError.invalidLifecycle }
        } else {
            guard let ref, !ref.isEmpty, ref.count <= 500, let date, date <= now else { throw CompanyConnectionError.invalidLifecycle }
        }
        self.stage = stage; self.rationale = text; self.sourceRef = ref; self.occurredAt = date
        expectedRevision = state.revision; expectedDecisionRevision = state.decisionRevision
        correctOutcome = state.latest?.stage.isOutcome == true
    }
}

struct CompanyLifecycleAttestation: Codable, Equatable, Sendable {
    let stage: CompanyLifecycleStage
    let rationale: String
    let sourceRef: String?
    let occurredAt: Date?
    let expectedRevision: Int
    let expectedDecisionRevision: Int
    let correctOutcome: Bool
    let idempotencyKey: String

    init(draft: CompanyLifecycleDraft, key: String) {
        stage = draft.stage; rationale = draft.rationale; sourceRef = draft.sourceRef; occurredAt = draft.occurredAt
        expectedRevision = draft.expectedRevision; expectedDecisionRevision = draft.expectedDecisionRevision
        correctOutcome = draft.correctOutcome; idempotencyKey = key
    }
}

struct CompanyLifecycleEvent: Decodable, Identifiable, Sendable {
    let eventId: String
    let caseId: String
    let revision: Int
    let stage: CompanyLifecycleStage
    let memberId: String
    let createdAt: Date
    let attestation: CompanyLifecycleAttestation
    let readinessStale: Bool
    let origin: String
    let externalFactVerified: Bool
    let externalSubmissionAllowed: Bool
    var id: String { eventId }
    func matches(caseID: String) -> Bool {
        caseId == caseID && revision > 0 && revision <= 50 && origin == "HUMAN_ATTESTATION" &&
        !externalFactVerified && !externalSubmissionAllowed && attestation.stage == stage && attestation.expectedRevision == revision - 1
    }
}

struct CompanyLifecycleState: Decodable, Sendable {
    let customerId: String
    let caseId: String
    let decisionRevision: Int
    let decisionAction: String?
    let revision: Int
    let latest: CompanyLifecycleEvent?
    let externalSubmissionAllowed: Bool
    func matches(_ identity: CompanyIdentity, item: CompanyCase) -> Bool {
        customerId == identity.customerId && caseId == item.caseId && !externalSubmissionAllowed &&
        decisionRevision == item.revision && decisionAction == item.decision?.action &&
        (0...50).contains(revision) && (revision == 0 ? latest == nil : latest?.matches(caseID: caseId) == true && latest?.revision == revision)
    }
    var options: [CompanyLifecycleStage] {
        guard revision < 50, decisionRevision > 0 else { return [] }
        if latest?.stage == .submitted { return CompanyLifecycleStage.allCases.filter(\.isOutcome) }
        if let stage = latest?.stage, stage.isOutcome { return CompanyLifecycleStage.allCases.filter { $0.isOutcome && $0 != stage } }
        guard decisionAction == "GO" else { return [] }
        return [.preparing, .blocked, .ready] + (latest?.stage == .ready && latest?.readinessStale == false ? [.submitted] : [])
    }
}

struct CompanyLifecycleAttempt: Equatable, Sendable {
    let accountID: String
    let caseID: String
    let draft: CompanyLifecycleDraft
    let key: String
    static func prepare(previous: Self?, accountID: String, caseID: String, draft: CompanyLifecycleDraft) -> Self {
        if let previous, previous.accountID == accountID, previous.caseID == caseID, previous.draft == draft { return previous }
        return Self(accountID: accountID, caseID: caseID, draft: draft, key: UUID().uuidString)
    }
    var payload: CompanyLifecycleAttestation { .init(draft: draft, key: key) }
    func accepts(_ event: CompanyLifecycleEvent, memberID: String) -> Bool {
        event.matches(caseID: caseID) && event.memberId == memberID && event.attestation == payload
    }
}

struct CompanyLifecycleHistory: Decodable, Sendable {
    let customerId: String
    let caseId: String
    let items: [CompanyLifecycleEvent]
    let hasMore: Bool
    let externalSubmissionAllowed: Bool
    func matches(_ identity: CompanyIdentity, caseID: String) -> Bool {
        customerId == identity.customerId && caseId == caseID && !externalSubmissionAllowed && items.count <= 50 && items.allSatisfy { $0.matches(caseID: caseID) } && Set(items.map(\.revision)).count == items.count
    }
}

struct CompanyLifecycleRate: Decodable, Sendable {
    let numerator: Int
    let denominator: Int
    let rate: Double?
    var valid: Bool {
        numerator >= 0 && denominator >= numerator && (denominator == 0 ? rate == nil : rate.map { $0.isFinite && abs($0 - Double(numerator)/Double(denominator)) < 1e-9 } == true)
    }
    var display: String { rate.map { String(format: "%.1f%%", $0*100) + " (\(numerator)/\(denominator))" } ?? "Нет данных" }
}

struct CompanyLifecycleMetrics: Decodable, Sendable {
    let customerId: String
    let asOf: Date
    let scope: String
    let savedCases: Int
    let everGoCases: Int
    let recordedSubmissions: Int
    let stageCounts: [String: Int]
    let goToSubmission: CompanyLifecycleRate
    let winRate: CompanyLifecycleRate
    let externalFactsVerified: Bool
    let marketCoverageComplete: Bool
    let contractRevenueVerified: Bool
    func matches(_ identity: CompanyIdentity) -> Bool {
        let stages = Set(CompanyLifecycleStage.allCases.map(\.rawValue) + ["UNRECORDED"])
        guard customerId == identity.customerId, scope == "ALL_TIME_SAVED_CASES_HUMAN_ATTESTATIONS", !externalFactsVerified, !marketCoverageComplete, !contractRevenueVerified,
              Set(stageCounts.keys) == stages, stageCounts.values.allSatisfy({ $0 >= 0 && $0 <= Int.max/16 }),
              savedCases == stageCounts.values.reduce(0,+), savedCases >= everGoCases, everGoCases >= recordedSubmissions, recordedSubmissions >= 0,
              goToSubmission.valid, winRate.valid, goToSubmission.numerator == recordedSubmissions, goToSubmission.denominator == everGoCases else { return false }
        let submissions = CompanyLifecycleStage.allCases.filter { !$0.isPreparation }.reduce(0) { $0 + (stageCounts[$1.rawValue] ?? 0) }
        return submissions == recordedSubmissions && winRate.numerator == stageCounts["WON"] && winRate.denominator == ["WON","LOST","REJECTED"].reduce(0) { $0 + (stageCounts[$1] ?? 0) }
    }
}

struct CompanyReadinessProjection: Decodable, Sendable {
    let schema: String
    let customerId: String
    let caseId: String
    let attemptId: String
    let cardSha256: String
    let candidateCount: Int
    let rejectedOrOpaqueLinks: Int
    let issues: [String]
    let partialReviewResolved: Bool
    let coverageComplete: Bool
    let platformOriginalVerified: Bool
    let qualificationVerified: Bool
    let externalSubmissionAllowed: Bool
}

struct CompanyReadinessBinding: Decodable, Sendable {
    let readyEventId: String
    let projectionSha256: String
    let projection: CompanyReadinessProjection
    let bindingId: String?
    let boundProjectionSha256: String?
    let bindingCurrent: Bool
    let qualificationVerified: Bool
    let externalSubmissionAllowed: Bool
    func matches(_ identity: CompanyIdentity, item: CompanyCase, event: CompanyLifecycleEvent) -> Bool {
        let p = projection
        return item.isCommercial && event.matches(caseID: item.caseId) && event.stage == .ready && !event.readinessStale && readyEventId == event.eventId &&
            p.schema == "commercial_readiness_partial_v1" && p.customerId == identity.customerId && p.caseId == item.caseId &&
            CompanyArtifactBytes.validDigest(projectionSha256) && CompanyArtifactBytes.validDigest(p.cardSha256) &&
            p.candidateCount >= 0 && p.rejectedOrOpaqueLinks >= 0 && p.partialReviewResolved == p.issues.isEmpty &&
            !p.coverageComplete && !p.platformOriginalVerified && !p.qualificationVerified && !p.externalSubmissionAllowed && !qualificationVerified && !externalSubmissionAllowed &&
            (bindingId == nil ? boundProjectionSha256 == nil : boundProjectionSha256.map(CompanyArtifactBytes.validDigest) == true) &&
            bindingCurrent == (bindingId != nil && boundProjectionSha256 == projectionSha256 && p.partialReviewResolved)
    }
    var canBind: Bool { projection.partialReviewResolved && bindingId == nil }
}

struct CompanyArtifactBytes: Sendable {
    static let limit = 2 * 1024 * 1024
    static let formats = ["pdf", "docx", "xlsx"]
    let data: Data
    let format: String
    var sha256: String { Self.digest(data) }
    static func digest(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
    static func validDigest(_ s: String) -> Bool { s.utf8.count == 64 && s.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) } }
    init(data: Data, format: String) throws {
        guard Self.formats.contains(format), !data.isEmpty, data.count <= Self.limit else { throw CompanyConnectionError.invalidArtifact }
        self.data = data; self.format = format
    }
    static func read(_ url: URL) throws -> Self {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        let format = url.pathExtension.lowercased()
        guard formats.contains(format), try url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true else { throw CompanyConnectionError.invalidArtifact }
        let handle = try FileHandle(forReadingFrom: url); defer { try? handle.close() }
        var data = Data()
        while data.count <= limit {
            guard let chunk = try handle.read(upToCount: min(65536, limit + 1 - data.count)), !chunk.isEmpty else { break }
            data.append(chunk)
        }
        return try Self(data: data, format: format)
    }
}

struct CompanyEventArtifact: Decodable, Sendable {
    struct Inspection: Decodable, Sendable {
        let sha256: String
        let sizeBytes: Int
        let formatHint: String
    }
    let customerId: String
    let caseId: String
    let eventId: String
    let eventRevision: Int
    let eventStage: CompanyLifecycleStage
    let artifactId: String
    let artifactKind: String
    let formatHint: String
    let inspection: Inspection
    let origin: String
    let storedBytesReverified: Bool
    let platformOriginalVerified: Bool
    let externalFactVerified: Bool
    let externalSubmissionAllowed: Bool
    func matches(_ identity: CompanyIdentity, event: CompanyLifecycleEvent) -> Bool {
        customerId == identity.customerId && event.matches(caseID: caseId) && eventId == event.eventId && eventRevision == event.revision && eventStage == event.stage &&
        !event.stage.isPreparation && artifactKind == (event.stage == .submitted ? "SUBMISSION_RECEIPT" : "OUTCOME_PROTOCOL") &&
        CompanyArtifactBytes.formats.contains(formatHint) && inspection.formatHint == formatHint && CompanyArtifactBytes.validDigest(inspection.sha256) &&
        (1...CompanyArtifactBytes.limit).contains(inspection.sizeBytes) && origin == "USER_SUPPLIED_UNATTESTED" && storedBytesReverified && !platformOriginalVerified && !externalFactVerified && !externalSubmissionAllowed
    }
    func accepts(_ bytes: CompanyArtifactBytes) -> Bool { formatHint == bytes.format && inspection.sizeBytes == bytes.data.count && inspection.sha256 == bytes.sha256 }
    var filename: String { "lifecycle-\(inspection.sha256.prefix(16)).\(formatHint)" }
}

struct CompanyPriceInput: Codable, Equatable, Sendable {
    var externalDirectRub = ""
    var ownLaborRub = ""
    var cashOverheadRub = ""
    var reserveRub = ""
    var fixedPlatformFeesRub = ""
    var guaranteeFinancingCostRub = ""
    var revenueTaxPercent = ""
    var variablePlatformFeePercent = ""
    var minimumProfitRub = ""
    var targetProfitRub = ""
    var referenceCeilingRub: String?
    var manualBidPricesRub: [String] = []
    var assumptionNote = ""
    var acceptHypotheticalAssumptionsOnly = false

    static func money(_ value: String) -> Bool { value.range(of: #"^[0-9]{1,12}(\.[0-9]{1,2})?$"#, options: .regularExpression) != nil }
    static func percent(_ value: String) -> Bool { value.range(of: #"^[0-9]{1,3}(\.[0-9]{1,4})?$"#, options: .regularExpression) != nil }
    static func normalize(_ value: String) -> String { value.trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: ",", with: ".") }
    static func decimal(_ value: String) -> Decimal? { Decimal(string: value, locale: Locale(identifier: "en_US_POSIX")) }
    var valid: Bool {
        let costs = [externalDirectRub, ownLaborRub, cashOverheadRub, reserveRub, fixedPlatformFeesRub, guaranteeFinancingCostRub]
        guard (costs + [minimumProfitRub, targetProfitRub]).allSatisfy(Self.money), costs.contains(where: { (Self.decimal($0) ?? 0) > 0 }),
              [revenueTaxPercent, variablePlatformFeePercent].allSatisfy(Self.percent),
              let tax = Self.decimal(revenueTaxPercent), let fee = Self.decimal(variablePlatformFeePercent), tax + fee < 100,
              let minimum = Self.decimal(minimumProfitRub), let target = Self.decimal(targetProfitRub), minimum <= target,
              manualBidPricesRub.count <= 8, manualBidPricesRub.allSatisfy({ Self.money($0) && (Self.decimal($0) ?? 0) > 0 }),
              Set(manualBidPricesRub.compactMap(Self.decimal)).count == manualBidPricesRub.count,
              !assumptionNote.isEmpty, assumptionNote.count <= 2000, assumptionNote == assumptionNote.trimmingCharacters(in: .whitespacesAndNewlines), acceptHypotheticalAssumptionsOnly else { return false }
        return referenceCeilingRub.map { Self.money($0) && (Self.decimal($0) ?? 0) > 0 } ?? true
    }
}

enum CompanyCostCategory: String, Codable, CaseIterable, Identifiable, Sendable {
    case direct = "external_direct_rub", labor = "own_labor_rub", overhead = "cash_overhead_rub", reserve = "reserve_rub", platform = "fixed_platform_fees_rub", financing = "guarantee_financing_cost_rub"
    var id: String { rawValue }
    var title: String {
        switch self { case .direct: "Прямые расходы"; case .labor: "Собственный труд"; case .overhead: "Накладные расходы"; case .reserve: "Резерв"; case .platform: "Сборы ЭТП"; case .financing: "Финансирование" }
    }
}
enum CompanyCostSource: String, Codable, CaseIterable, Identifiable, Sendable {
    case assumption = "ASSUMPTION", quote = "USER_REPORTED_QUOTE", actual = "USER_REPORTED_ACTUAL", approvedNorm = "APPROVED_CORPORATE_NORM"
    var id: String { rawValue }
    var title: String { switch self { case .assumption: "Допущение"; case .quote: "КП со слов сотрудника"; case .actual: "Расходы со слов сотрудника"; case .approvedNorm: "Утверждённый корпоративный норматив" } }
}
struct CompanyNormBinding: Codable, Equatable, Sendable {
    let normId:String;let normKey:String;let revision:Int;let recordSha256:String
    var valid:Bool {
        !normId.isEmpty && normId.count<=36 && (1...99).contains(revision) && CompanyNormDigest.isSHA(normKey) && CompanyNormDigest.isSHA(recordSha256)
    }
}
struct CompanyCostLine: Codable, Equatable, Sendable {
    var category: CompanyCostCategory = .direct
    var title = ""
    var unit = ""
    var quantity = ""
    var rateRub = ""
    var sourceKind: CompanyCostSource = .assumption
    var sourceNote = ""
    var normBinding:CompanyNormBinding? = nil
    static func fromNorm(_ record:CompanyNormRecord,identity:CompanyIdentity)throws->Self {
        guard record.matches(identity),record.action=="APPROVED",let quantity=record.result.normQuantity,let rate=record.result.normRateRub else{throw CompanyConnectionError.invalidPrice}
        let line=Self(category:record.result.category,title:record.result.title,unit:record.result.unit,quantity:quantity,rateRub:rate,sourceKind:.approvedNorm,sourceNote:"Явно выбранный корпоративный норматив v"+String(record.revision),normBinding:.init(normId:record.normId,normKey:record.normKey,revision:record.revision,recordSha256:record.recordSha256))
        guard line.amount != nil else{throw CompanyConnectionError.invalidPrice};return line
    }
    var validBinding:Bool {
        if sourceKind == .approvedNorm {return normBinding?.valid == true && [.labor,.direct,.overhead].contains(category)}
        return normBinding==nil
    }
    var normalized: Self {
        var x = self
        x.title = title.trimmingCharacters(in:.whitespacesAndNewlines); x.unit = unit.trimmingCharacters(in:.whitespacesAndNewlines)
        x.quantity = CompanyPriceInput.normalize(quantity); x.rateRub = CompanyPriceInput.normalize(rateRub)
        x.sourceNote = sourceNote.trimmingCharacters(in:.whitespacesAndNewlines); return x
    }
    var amount: Decimal? {
        guard validBinding, self == normalized, !title.isEmpty, title.count <= 160, !unit.isEmpty, unit.count <= 24, !sourceNote.isEmpty, sourceNote.count <= 500,
              quantity.range(of: #"^[0-9]{1,9}(\.[0-9]{1,4})?$"#,options:.regularExpression) != nil,
              CompanyPriceInput.money(rateRub), let q = CompanyPriceInput.decimal(quantity), let r = CompanyPriceInput.decimal(rateRub), q > 0, r > 0 else { return nil }
        var product = q*r; var rounded = Decimal(); NSDecimalRound(&rounded,&product,2,.up); return rounded
    }
}
struct CompanyPriceTerms: Codable, Equatable, Sendable {
    let revenueTaxPercent: String
    let variablePlatformFeePercent: String
    let minimumProfitRub: String
    let targetProfitRub: String
    let referenceCeilingRub: String?
    let manualBidPricesRub: [String]
    let assumptionNote: String
    let acceptHypotheticalAssumptionsOnly: Bool
    init(_ input: CompanyPriceInput) {
        revenueTaxPercent=input.revenueTaxPercent; variablePlatformFeePercent=input.variablePlatformFeePercent; minimumProfitRub=input.minimumProfitRub; targetProfitRub=input.targetProfitRub
        referenceCeilingRub=input.referenceCeilingRub; manualBidPricesRub=input.manualBidPricesRub; assumptionNote=input.assumptionNote; acceptHypotheticalAssumptionsOnly=input.acceptHypotheticalAssumptionsOnly
    }
    func aggregate(_ sums: [String:String]) -> CompanyPriceInput {
        var x = CompanyPriceInput(); x.revenueTaxPercent=revenueTaxPercent; x.variablePlatformFeePercent=variablePlatformFeePercent; x.minimumProfitRub=minimumProfitRub; x.targetProfitRub=targetProfitRub; x.referenceCeilingRub=referenceCeilingRub; x.manualBidPricesRub=manualBidPricesRub; x.assumptionNote=assumptionNote; x.acceptHypotheticalAssumptionsOnly=acceptHypotheticalAssumptionsOnly
        x.externalDirectRub=sums[CompanyCostCategory.direct.rawValue] ?? ""; x.ownLaborRub=sums[CompanyCostCategory.labor.rawValue] ?? ""; x.cashOverheadRub=sums[CompanyCostCategory.overhead.rawValue] ?? ""; x.reserveRub=sums[CompanyCostCategory.reserve.rawValue] ?? ""; x.fixedPlatformFeesRub=sums[CompanyCostCategory.platform.rawValue] ?? ""; x.guaranteeFinancingCostRub=sums[CompanyCostCategory.financing.rawValue] ?? ""
        return x
    }
}
struct CompanyItemizedInput: Codable, Equatable, Sendable {
    let lines: [CompanyCostLine]
    let zeroCostCategories: [CompanyCostCategory]
    let terms: CompanyPriceTerms
    let confirmNoDoubleCount: Bool
    var sums: [String:Decimal]? {
        let used=Set(lines.map(\.category)), zeros=Set(zeroCostCategories)
        let bindings=lines.compactMap{$0.normBinding?.normId}
        guard Set(bindings).count==bindings.count else{return nil}
        guard confirmNoDoubleCount, (1...60).contains(lines.count), zeros.count==zeroCostCategories.count, used.isDisjoint(with:zeros), used.union(zeros)==Set(CompanyCostCategory.allCases) else { return nil }
        var sums=Dictionary(uniqueKeysWithValues:CompanyCostCategory.allCases.map { ($0.rawValue,Decimal(0)) })
        for line in lines { guard let amount=line.amount else { return nil }; sums[line.category.rawValue,default:0]+=amount }
        guard sums.values.allSatisfy({ $0 <= Decimal(string:"999999999999.99")! }) else { return nil }; return sums
    }
}
struct CompanyProjectedCostLine: Codable, Equatable, Sendable, Identifiable {
    let ordinal: Int
    let category: CompanyCostCategory
    let title: String
    let unit: String
    let quantity: String
    let rateRub: String
    let sourceKind: CompanyCostSource
    let sourceNote: String
    let amountRub: String
    let normBinding:CompanyNormBinding?
    var id: Int { ordinal }
    var line: CompanyCostLine { .init(category:category,title:title,unit:unit,quantity:quantity,rateRub:rateRub,sourceKind:sourceKind,sourceNote:sourceNote,normBinding:normBinding) }
}
struct CompanyItemizedProjection: Codable, Equatable, Sendable {
    let schema: String
    let inputs: CompanyItemizedInput
    let lines: [CompanyProjectedCostLine]
    let categoryTotalsRub: [String:String]
    let roundingPolicy: String
    let sourceNotesIndependentlyVerified: Bool
    let doubleCountIndependentlyChecked: Bool
    let externalSubmissionAllowed: Bool
    func matches(_ aggregate: CompanyPriceInput, expected: CompanyItemizedInput? = nil) -> Bool {
        func cents(_ value: String) -> Decimal? {
            guard value.range(of: #"^[0-9]{1,12}\.[0-9]{2}$"#,options:.regularExpression) != nil else { return nil }
            return CompanyPriceInput.decimal(value)
        }
        guard schema == "company_price_itemized_v1", roundingPolicy == "CEIL_EACH_LINE_TO_KOPECKS_THEN_SUM", !sourceNotesIndependentlyVerified, !doubleCountIndependentlyChecked, !externalSubmissionAllowed,
              expected.map({ $0 == inputs }) ?? true, let sums=inputs.sums, Set(categoryTotalsRub.keys)==Set(sums.keys), sums.allSatisfy({ cents(categoryTotalsRub[$0.key] ?? "") == $0.value }),
              aggregate.valid, inputs.terms.aggregate(categoryTotalsRub)==aggregate, lines.count==inputs.lines.count else { return false }
        return lines.enumerated().allSatisfy { i,row in row.ordinal==i+1 && row.line==inputs.lines[i] && cents(row.amountRub)==inputs.lines[i].amount }
    }
}
struct CompanyItemizedPreview: Decodable, Sendable {
    let customerId: String
    let caseId: String
    let inputsStored: Bool
    let inputs: CompanyPriceInput
    let itemizedEstimate: CompanyItemizedProjection
    let result: CompanyPriceResult
    func matches(_ identity: CompanyIdentity, caseID: String, estimate: CompanyItemizedInput) -> Bool {
        customerId==identity.customerId && caseId==caseID && !inputsStored && itemizedEstimate.matches(inputs,expected:estimate) && result.matches(inputs)
    }
}
struct CompanyItemizedSavePayload: Encodable {
    let expectedRevision: Int
    let idempotencyKey: String
    let estimate: CompanyItemizedInput
}

struct CompanyPriceRow: Codable, Equatable, Sendable, Identifiable {
    let kind: String
    let priceRub: String
    let cashSurplusRub: String
    let economicProfitRub: String
    let economicMarginPercent: String?
    let cashBreakEvenMet: Bool
    let fullBreakEvenMet: Bool
    let minimumProfitMet: Bool
    let targetProfitMet: Bool
    let withinUserReferenceCeiling: Bool?
    var id: String { kind + ":" + priceRub }
    var title: String {
        switch kind {
        case "CASH_BREAK_EVEN": "Денежная безубыточность"
        case "FULL_BREAK_EVEN": "Полная безубыточность"
        case "STRATEGIC_MINIMUM_PROFIT": "Минимальная прибыль"
        case "COMMERCIAL_TARGET_PROFIT": "Целевая прибыль"
        default: "Ручная цена"
        }
    }
}

struct CompanyPriceResult: Codable, Equatable, Sendable {
    static let kinds = ["CASH_BREAK_EVEN", "FULL_BREAK_EVEN", "STRATEGIC_MINIMUM_PROFIT", "COMMERCIAL_TARGET_PROFIT"]
    let schema: String
    let currency: String
    let cashFixedAndReservedRub: String
    let ownLaborRub: String
    let fullEconomicCostBeforeRevenueRatesRub: String
    let revenueRetentionRate: String
    let thresholdsRoundedUpToKopecks: Bool
    let profitsRoundedDownToKopecks: Bool
    let scenarios: [CompanyPriceRow]
    let referenceCeilingUserSupplied: Bool
    let assumptionsIndependentlyVerified: Bool
    let taxModelVerified: Bool
    let marketComparablesUsed: Bool
    let probabilityOfWinningEstimated: Bool
    let isProcurementBidRecommendation: Bool
    let commercialOwnerGo: Bool
    let externalSubmissionAllowed: Bool
    func matches(_ input: CompanyPriceInput) -> Bool {
        func money(_ s: String) -> Bool { s.range(of: #"^-?[0-9]{1,21}\.[0-9]{2}$"#, options: .regularExpression) != nil }
        guard input.valid, schema == "company_price_scenario_v1", currency == "RUB", thresholdsRoundedUpToKopecks, profitsRoundedDownToKopecks,
              !assumptionsIndependentlyVerified, !taxModelVerified, !marketComparablesUsed, !probabilityOfWinningEstimated, !isProcurementBidRecommendation, !commercialOwnerGo, !externalSubmissionAllowed,
              referenceCeilingUserSupplied == (input.referenceCeilingRub != nil),
              [cashFixedAndReservedRub, ownLaborRub, fullEconomicCostBeforeRevenueRatesRub].allSatisfy(money),
              let retention = CompanyPriceInput.decimal(revenueRetentionRate), retention > 0, retention <= 1,
              scenarios.count == 4 + input.manualBidPricesRub.count else { return false }
        for (i,row) in scenarios.enumerated() {
            guard row.kind == (i < 4 ? Self.kinds[i] : "MANUAL_PRICE"), [row.priceRub,row.cashSurplusRub,row.economicProfitRub].allSatisfy(money),
                  let price = CompanyPriceInput.decimal(row.priceRub), price >= 0,
                  (price == 0 ? row.economicMarginPercent == nil : row.economicMarginPercent?.range(of: #"^-?[0-9]{1,24}\.[0-9]{4}$"#, options: .regularExpression) != nil),
                  row.withinUserReferenceCeiling == input.referenceCeilingRub.flatMap(CompanyPriceInput.decimal).map({ price <= $0 }) else { return false }
            if i >= 4, price != CompanyPriceInput.decimal(input.manualBidPricesRub[i-4]) { return false }
        }
        return true
    }
}

struct CompanyPricePreview: Decodable, Sendable {
    let customerId: String
    let caseId: String
    let inputsStored: Bool
    let result: CompanyPriceResult
    func matches(_ identity: CompanyIdentity, caseID: String, input: CompanyPriceInput) -> Bool {
        customerId == identity.customerId && caseId == caseID && !inputsStored && result.matches(input)
    }
}

struct CompanyPriceRecord: Decodable, Identifiable, Sendable {
    let customerId: String
    let caseId: String
    let scenarioId: String
    let revision: Int
    let memberId: String
    let createdAt: Date
    let inputs: CompanyPriceInput
    let result: CompanyPriceResult
    let itemizedEstimate: CompanyItemizedProjection?
    let origin: String
    let externalSubmissionAllowed: Bool
    var id: String { scenarioId }
    func matches(_ identity: CompanyIdentity, caseID: String) -> Bool {
        customerId == identity.customerId && caseId == caseID && UUID(uuidString: scenarioId) != nil && (1...30).contains(revision) && origin == "EXPLICIT_USER_ASSUMPTIONS" && !externalSubmissionAllowed && result.matches(inputs) && (itemizedEstimate.map { $0.matches(inputs) } ?? true)
    }
}

enum CompanyCostDocumentKind: String, Codable, CaseIterable, Identifiable, Sendable {
    case quote = "QUOTE", invoice = "INVOICE", contract = "CONTRACT", timesheet = "TIMESHEET", other = "OTHER"
    var id: String { rawValue }
    var title: String { switch self { case .quote: "Коммерческое предложение"; case .invoice: "Счёт"; case .contract: "Договор"; case .timesheet: "Табель трудозатрат"; case .other: "Прочее" } }
}

struct CompanyCostTarget: Sendable {
    let scenario: CompanyPriceRecord
    let line: CompanyProjectedCostLine
    // Python json.dumps(ensure_ascii=False, sort_keys=True, separators=(',', ':')).
    fileprivate static func quote(_ value: String) -> String {
        var out = "\""
        for scalar in value.unicodeScalars {
            switch scalar.value {
            case 34: out += "\\\""
            case 92: out += "\\\\"
            case 8: out += "\\b"
            case 9: out += "\\t"
            case 10: out += "\\n"
            case 12: out += "\\f"
            case 13: out += "\\r"
            case 0...31: out += String(format:"\\u%04x",scalar.value)
            default: out.unicodeScalars.append(scalar)
            }
        }
        return out + "\""
    }
    var digest: String {
        let values = ["amount_rub":line.amountRub,"category":line.category.rawValue,"quantity":line.quantity,"rate_rub":line.rateRub,"source_kind":line.sourceKind.rawValue,"source_note":line.sourceNote,"title":line.title,"unit":line.unit]
        if line.normBinding != nil {
            // All nested keys, including numeric revision, use the Python canonical form.
            guard let object=try? CompanyNormDigest.object(line),
                  let text=try? CompanyActualBaseline.canonical(["line":object,"revision":scenario.revision,"scenario_id":scenario.scenarioId]) else{return ""}
            return CompanyArtifactBytes.digest(Data(text.utf8))
        }
        let keys = (Array(values.keys) + ["ordinal"]).sorted()
        let row = keys.map { Self.quote($0) + ":" + ($0 == "ordinal" ? String(line.ordinal) : Self.quote(values[$0]!)) }.joined(separator:",")
        let text = "{\"line\":{\(row)},\"revision\":\(scenario.revision),\"scenario_id\":\(Self.quote(scenario.scenarioId))}"
        return CompanyArtifactBytes.digest(Data(text.utf8))
    }
    func matches(_ identity: CompanyIdentity, caseID: String) -> Bool {
        scenario.matches(identity,caseID:caseID) && scenario.itemizedEstimate?.lines.contains(line) == true
    }
}

struct CompanyCostScope: Decodable, Equatable, Sendable {
    let customerId: String
    let caseId: String
    let scenarioId: String
    let scenarioRevision: Int
    let lineOrdinal: Int
    let lineSha256: String
    let lineTitle: String
    let lineAmountRub: String
    let externalSubmissionAllowed: Bool
    func matches(_ identity: CompanyIdentity, caseID: String, target: CompanyCostTarget) -> Bool {
        target.matches(identity,caseID:caseID) && customerId==identity.customerId && self.caseId==caseID && scenarioId==target.scenario.scenarioId && scenarioRevision==target.scenario.revision && lineOrdinal==target.line.ordinal && lineTitle==target.line.title && lineAmountRub==target.line.amountRub && lineSha256==target.digest && !externalSubmissionAllowed
    }
}
struct CompanyCostInspection: Decodable, Equatable, Sendable {
    let schema: String
    let sha256: String
    let sizeBytes: Int
    let formatHint: String
    let formatCheck: String
    let textPreviewComplete: Bool
    let requirementsVerified: Bool
    let malwareFreeVerified: Bool
    let digitalSignatureVerified: Bool
    private enum CodingKeys: String,CodingKey { case schema,sha256,sizeBytes,formatHint,formatCheck,textPreviewComplete,requirementsVerified,malwareFreeVerified,digitalSignatureVerified,textPreview }
    init(from decoder: Decoder) throws {
        let c=try decoder.container(keyedBy:CodingKeys.self)
        guard !c.contains(.textPreview) else { throw CompanyConnectionError.invalidArtifact }
        schema=try c.decode(String.self,forKey:.schema); sha256=try c.decode(String.self,forKey:.sha256); sizeBytes=try c.decode(Int.self,forKey:.sizeBytes); formatHint=try c.decode(String.self,forKey:.formatHint); formatCheck=try c.decode(String.self,forKey:.formatCheck)
        textPreviewComplete=try c.decode(Bool.self,forKey:.textPreviewComplete); requirementsVerified=try c.decode(Bool.self,forKey:.requirementsVerified); malwareFreeVerified=try c.decode(Bool.self,forKey:.malwareFreeVerified); digitalSignatureVerified=try c.decode(Bool.self,forKey:.digitalSignatureVerified)
    }
    var valid: Bool { schema=="commercial_attachment_inspection_v1" && CompanyArtifactBytes.validDigest(sha256) && (1...CompanyArtifactBytes.limit).contains(sizeBytes) && CompanyArtifactBytes.formats.contains(formatHint) && formatCheck==(formatHint=="pdf" ? "PDF_HEADER_AND_EOF_ONLY" : "BOUNDED_OOXML_PACKAGE_CHECK") && !textPreviewComplete && !requirementsVerified && !malwareFreeVerified && !digitalSignatureVerified }
}
struct CompanyCostEvidence: Decodable, Equatable, Sendable {
    let scope: CompanyCostScope
    let evidenceId: String
    let memberId: String
    let documentKind: CompanyCostDocumentKind
    let formatHint: String
    let inspection: CompanyCostInspection
    let origin: String
    let storedBytesReverified: Bool
    let documentOriginVerified: Bool
    let costAmountVerified: Bool
    let paymentVerified: Bool
    private enum CodingKeys: String,CodingKey { case evidenceId,memberId,documentKind,formatHint,inspection,origin,storedBytesReverified,documentOriginVerified,costAmountVerified,paymentVerified }
    init(from decoder: Decoder) throws {
        scope=try CompanyCostScope(from:decoder); let c=try decoder.container(keyedBy:CodingKeys.self)
        evidenceId=try c.decode(String.self,forKey:.evidenceId); memberId=try c.decode(String.self,forKey:.memberId); documentKind=try c.decode(CompanyCostDocumentKind.self,forKey:.documentKind); formatHint=try c.decode(String.self,forKey:.formatHint); inspection=try c.decode(CompanyCostInspection.self,forKey:.inspection); origin=try c.decode(String.self,forKey:.origin); storedBytesReverified=try c.decode(Bool.self,forKey:.storedBytesReverified); documentOriginVerified=try c.decode(Bool.self,forKey:.documentOriginVerified); costAmountVerified=try c.decode(Bool.self,forKey:.costAmountVerified); paymentVerified=try c.decode(Bool.self,forKey:.paymentVerified)
    }
    func matches(_ identity: CompanyIdentity, caseID: String,target: CompanyCostTarget) -> Bool {
        scope.matches(identity,caseID:caseID,target:target) && UUID(uuidString:evidenceId) != nil && !memberId.isEmpty && inspection.valid && formatHint==inspection.formatHint && origin=="USER_SUPPLIED_UNATTESTED" && storedBytesReverified && !documentOriginVerified && !costAmountVerified && !paymentVerified
    }
    func accepts(_ bytes: CompanyArtifactBytes) -> Bool { formatHint==bytes.format && inspection.sizeBytes==bytes.data.count && inspection.sha256==bytes.sha256 }
    var filename: String { "cost-\(inspection.sha256.prefix(16)).\(formatHint)" }
}
struct CompanyCostBinding: Decodable, Sendable {
    let scope: CompanyCostScope
    let evidence: CompanyCostEvidence?
    private enum CodingKeys: String,CodingKey { case evidence }
    init(from decoder: Decoder) throws {
        scope=try CompanyCostScope(from:decoder); let c=try decoder.container(keyedBy:CodingKeys.self)
        guard c.contains(.evidence) else { throw CompanyConnectionError.invalidResponse }
        evidence=try c.decodeIfPresent(CompanyCostEvidence.self,forKey:.evidence)
    }
    func matches(_ identity: CompanyIdentity, caseID: String,target: CompanyCostTarget) -> Bool { scope.matches(identity,caseID:caseID,target:target) && (evidence.map { $0.scope==scope && $0.matches(identity,caseID:caseID,target:target) } ?? true) }
}

struct CompanyActualBaseline: Sendable {
    let scenario: CompanyPriceRecord
    fileprivate static func canonical(_ value: Any) throws -> String {
        if let obj=value as? [String:Any] { return "{" + (try obj.keys.sorted().map { key in CompanyCostTarget.quote(key) + ":" + (try canonical(obj[key]!)) }).joined(separator:",") + "}" }
        if let arr=value as? [Any] { return "[" + (try arr.map(canonical)).joined(separator:",") + "]" }
        if let string=value as? String { return CompanyCostTarget.quote(string) }
        return String(decoding:try JSONSerialization.data(withJSONObject:value,options:[.fragmentsAllowed]),as:UTF8.self)
    }
    func digest() throws -> String {
        guard let estimate=scenario.itemizedEstimate,estimate.matches(scenario.inputs) else { throw CompanyConnectionError.invalidPrice }
        let encoder=JSONEncoder();encoder.keyEncodingStrategy = .convertToSnakeCase
        guard var object=try JSONSerialization.jsonObject(with:encoder.encode(estimate)) as? [String:Any],var input=object["inputs"] as? [String:Any],var terms=input["terms"] as? [String:Any] else { throw CompanyConnectionError.invalidPrice }
        if terms["reference_ceiling_rub"]==nil { terms["reference_ceiling_rub"]=NSNull() };input["terms"]=terms;object["inputs"]=input
        return CompanyArtifactBytes.digest(Data(try Self.canonical(["scenario_id":scenario.scenarioId,"revision":scenario.revision,"estimate":object]).utf8))
    }
}
struct CompanyActualObservation: Codable, Equatable, Sendable {
    let ordinal: Int
    var quantity: String
    var rateRub: String
    var sourceNote: String
    var amount: Decimal? {
        guard quantity.range(of:#"^[0-9]{1,9}(\.[0-9]{1,4})?$"#,options:.regularExpression) != nil,CompanyPriceInput.money(rateRub),let q=CompanyPriceInput.decimal(quantity),let r=CompanyPriceInput.decimal(rateRub),q != 0 || r == 0,!sourceNote.isEmpty,sourceNote.count<=500,sourceNote==sourceNote.trimmingCharacters(in:.whitespacesAndNewlines) else { return nil }
        var product=q*r;var rounded=Decimal();NSDecimalRound(&rounded,&product,2,.up);return rounded
    }
}
struct CompanyActualInput: Codable, Equatable, Sendable {
    let baselineSha256: String
    let asOf: String
    let observations: [CompanyActualObservation]
    let unplannedCosts: [CompanyCostLine]
    let note: String
    let confirmCumulativeUserReport: Bool
    let confirmNoDoubleCount: Bool
    func valid(_ baseline: CompanyActualBaseline) -> Bool {
        guard baselineSha256==(try? baseline.digest()),let lines=baseline.scenario.itemizedEstimate?.lines,asOf.range(of:#"^\d{4}-\d{2}-\d{2}$"#,options:.regularExpression) != nil,confirmCumulativeUserReport,confirmNoDoubleCount,!note.isEmpty,note.count<=2000,note==note.trimmingCharacters(in:.whitespacesAndNewlines),observations.count<=60,unplannedCosts.count<=30,!observations.isEmpty || !unplannedCosts.isEmpty,Set(observations.map(\.ordinal)).count==observations.count else { return false }
        return observations.allSatisfy { o in o.amount != nil && lines.contains { $0.ordinal==o.ordinal } } && unplannedCosts.allSatisfy { $0.amount != nil && $0.sourceKind == .actual }
    }
}
struct CompanyActualRow: Codable, Equatable, Sendable, Identifiable {
    let ordinal:Int;let title:String;let category:CompanyCostCategory;let unit:String
    let plannedQuantity:String;let plannedRateRub:String;let plannedAmountRub:String
    let status:String;let actualQuantity:String?;let actualRateRub:String?;let actualAmountRub:String?;let varianceRub:String?;let variancePercent:String?;let sourceNote:String?
    var id:Int { ordinal }
}
struct CompanyActualExtra: Codable, Equatable, Sendable, Identifiable {
    let ordinal:Int;let category:CompanyCostCategory;let title:String;let unit:String;let quantity:String;let rateRub:String;let sourceKind:CompanyCostSource;let sourceNote:String;let actualAmountRub:String
    var id:Int { ordinal }
    var line:CompanyCostLine { .init(category:category,title:title,unit:unit,quantity:quantity,rateRub:rateRub,sourceKind:sourceKind,sourceNote:sourceNote) }
}
struct CompanyActualTotals: Decodable, Equatable, Sendable {
    let plannedRub:String;let matchedPlannedRub:String;let reportedPlannedLineActualRub:String;let reportedUnplannedRub:String;let reportedTotalRub:String;let missingPlannedLines:Int;let matchedVarianceRub:String?;let matchedVariancePercent:String?;let allPlannedLinesReported:Bool;let reportedVsFullPlanRub:String?
}
private struct CompanyActualAccumulator {
    var plan=Decimal(0),matched=Decimal(0),observed=Decimal(0),extra=Decimal(0);var missing=0
    mutating func add(_ x:Self) { plan+=x.plan;matched+=x.matched;observed+=x.observed;extra+=x.extra;missing+=x.missing }
    static func matches(_ value:String?,_ number:Decimal?,digits:Int=2) -> Bool {
        guard let number else { return value==nil };guard let value,value.range(of:"^-?[0-9]{1,24}\\.[0-9]{\(digits)}$",options:.regularExpression) != nil else { return false };return CompanyPriceInput.decimal(value)==number
    }
    static func percentage(_ delta:Decimal,_ base:Decimal)->Decimal? { guard base != 0 else { return nil };var x=delta/base*100,rounded=Decimal();NSDecimalRound(&rounded,&x,4,.plain);return rounded }
    func matches(_ t:CompanyActualTotals)->Bool {
        Self.matches(t.plannedRub,plan) && Self.matches(t.matchedPlannedRub,matched) && Self.matches(t.reportedPlannedLineActualRub,observed) && Self.matches(t.reportedUnplannedRub,extra) && Self.matches(t.reportedTotalRub,observed+extra) && t.missingPlannedLines==missing && Self.matches(t.matchedVarianceRub,matched==0 ? nil : observed-matched) && Self.matches(t.matchedVariancePercent,Self.percentage(observed-matched,matched),digits:4) && t.allPlannedLinesReported==(missing==0) && Self.matches(t.reportedVsFullPlanRub,missing==0 ? observed+extra-plan : nil)
    }
}
struct CompanyActualResult: Decodable, Equatable, Sendable {
    let schema:String;let currency:String;let baselineSha256:String;let asOf:String;let lines:[CompanyActualRow];let unplannedCosts:[CompanyActualExtra];let categoryTotals:[String:CompanyActualTotals];let totals:CompanyActualTotals
    let roundingPolicy:String;let basis:String;let origin:String;let paymentVerified:Bool;let actualAmountsIndependentlyVerified:Bool;let contractCostCoverageComplete:Bool;let contractExecutionVerified:Bool;let revenueOrProfitVerified:Bool;let externalSubmissionAllowed:Bool
    func matches(_ input:CompanyActualInput,baseline:CompanyActualBaseline)->Bool {
        guard input.valid(baseline),schema=="company_actual_cost_snapshot_v1",currency=="RUB",baselineSha256==input.baselineSha256,asOf==input.asOf,roundingPolicy=="CEIL_EACH_LINE_TO_KOPECKS_THEN_SUM",basis=="CUMULATIVE_USER_REPORTED_COSTS_BEFORE_REVENUE_RATES",origin=="USER_REPORTED_UNVERIFIED",!paymentVerified,!actualAmountsIndependentlyVerified,!contractCostCoverageComplete,!contractExecutionVerified,!revenueOrProfitVerified,!externalSubmissionAllowed,let planned=baseline.scenario.itemizedEstimate?.lines,planned.count==lines.count,unplannedCosts.count==input.unplannedCosts.count else { return false }
        var category=Dictionary(uniqueKeysWithValues:CompanyCostCategory.allCases.map { ($0.rawValue,CompanyActualAccumulator()) })
        for (l,row) in zip(planned,lines) {
            guard let plan=CompanyPriceInput.decimal(l.amountRub),row.ordinal==l.ordinal,row.title==l.title,row.category==l.category,row.unit==l.unit,row.plannedQuantity==l.quantity,row.plannedRateRub==l.rateRub,row.plannedAmountRub==l.amountRub else { return false }
            var t=category[l.category.rawValue]!;t.plan+=plan
            if let o=input.observations.first(where:{$0.ordinal==l.ordinal}),let a=o.amount {
                guard row.status=="USER_REPORTED_ACTUAL",row.actualQuantity==o.quantity,row.actualRateRub==o.rateRub,row.sourceNote==o.sourceNote,CompanyActualAccumulator.matches(row.actualAmountRub,a),CompanyActualAccumulator.matches(row.varianceRub,a-plan),CompanyActualAccumulator.matches(row.variancePercent,CompanyActualAccumulator.percentage(a-plan,plan),digits:4) else { return false };t.matched+=plan;t.observed+=a
            } else {
                guard row.status=="NOT_REPORTED",row.actualQuantity==nil,row.actualRateRub==nil,row.sourceNote==nil,row.actualAmountRub==nil,row.varianceRub==nil,row.variancePercent==nil else { return false };t.missing+=1
            };category[l.category.rawValue]=t
        }
        for (i,row) in unplannedCosts.enumerated() { let l=input.unplannedCosts[i];guard row.ordinal==i+1,row.line==l,let a=l.amount,CompanyActualAccumulator.matches(row.actualAmountRub,a) else { return false };category[l.category.rawValue]!.extra+=a }
        guard Set(category.keys)==Set(categoryTotals.keys) else { return false };var total=CompanyActualAccumulator()
        for (k,t) in category { guard t.observed+t.extra<=Decimal(string:"999999999999.99")!,let c=categoryTotals[k],t.matches(c) else { return false };total.add(t) };return total.matches(totals)
    }
}
struct CompanyActualScope: Decodable, Equatable, Sendable {
    let customerId:String;let caseId:String;let scenarioId:String;let scenarioRevision:Int;let baselineSha256:String;let externalSubmissionAllowed:Bool
    func matches(_ identity:CompanyIdentity,caseID:String,baseline:CompanyActualBaseline)->Bool { let s=baseline.scenario;return s.matches(identity,caseID:caseID)&&customerId==identity.customerId&&caseId==caseID&&scenarioId==s.scenarioId&&scenarioRevision==s.revision&&baselineSha256==(try? baseline.digest()) && !externalSubmissionAllowed }
}
struct CompanyActualPreview: Decodable, Sendable {
    let scope:CompanyActualScope;let inputsStored:Bool;let result:CompanyActualResult
    private enum CodingKeys:String,CodingKey {case inputsStored,result}
    init(from decoder:Decoder)throws {scope=try CompanyActualScope(from:decoder);let c=try decoder.container(keyedBy:CodingKeys.self);inputsStored=try c.decode(Bool.self,forKey:.inputsStored);result=try c.decode(CompanyActualResult.self,forKey:.result)}
    func matches(_ identity:CompanyIdentity,caseID:String,baseline:CompanyActualBaseline,input:CompanyActualInput)->Bool {scope.matches(identity,caseID:caseID,baseline:baseline) && !inputsStored && result.matches(input,baseline:baseline)}
}
struct CompanyActualRecord: Decodable, Identifiable, Sendable {
    let scope:CompanyActualScope;let snapshotId:String;let revision:Int;let memberId:String;let createdAt:Date;let inputs:CompanyActualInput;let result:CompanyActualResult
    var id:String { snapshotId }
    private enum CodingKeys:String,CodingKey {case snapshotId,revision,memberId,createdAt,inputs,result}
    init(from decoder:Decoder)throws {scope=try CompanyActualScope(from:decoder);let c=try decoder.container(keyedBy:CodingKeys.self);snapshotId=try c.decode(String.self,forKey:.snapshotId);revision=try c.decode(Int.self,forKey:.revision);memberId=try c.decode(String.self,forKey:.memberId);createdAt=try c.decode(Date.self,forKey:.createdAt);inputs=try c.decode(CompanyActualInput.self,forKey:.inputs);result=try c.decode(CompanyActualResult.self,forKey:.result)}
    func matches(_ identity:CompanyIdentity,caseID:String,baseline:CompanyActualBaseline)->Bool {scope.matches(identity,caseID:caseID,baseline:baseline)&&UUID(uuidString:snapshotId) != nil && (1...30).contains(revision) && !memberId.isEmpty && result.matches(inputs,baseline:baseline)}
}
struct CompanyActualPage:Decodable,Sendable {
    let scope:CompanyActualScope;let plannedLines:[CompanyProjectedCostLine];let items:[CompanyActualRecord];let hasMore:Bool
    private enum CodingKeys:String,CodingKey {case plannedLines,items,hasMore}
    init(from decoder:Decoder)throws {scope=try CompanyActualScope(from:decoder);let c=try decoder.container(keyedBy:CodingKeys.self);plannedLines=try c.decode([CompanyProjectedCostLine].self,forKey:.plannedLines);items=try c.decode([CompanyActualRecord].self,forKey:.items);hasMore=try c.decode(Bool.self,forKey:.hasMore)}
    func matches(_ identity:CompanyIdentity,caseID:String,baseline:CompanyActualBaseline)->Bool {scope.matches(identity,caseID:caseID,baseline:baseline)&&plannedLines==baseline.scenario.itemizedEstimate?.lines&&items.count<=10&&(!hasMore||items.count==10)&&items.allSatisfy{$0.matches(identity,caseID:caseID,baseline:baseline)}}
}
struct CompanyActualSave:Codable,Equatable,Sendable {let expectedRevision:Int;let idempotencyKey:String;let snapshot:CompanyActualInput}
struct CompanyActualAttempt:Equatable,Sendable {
    let accountID:String;let scenarioID:String;let payload:CompanyActualSave;let result:CompanyActualResult
    static func prepare(previous:Self?,accountID:String,baseline:CompanyActualBaseline,revision:Int,input:CompanyActualInput,result:CompanyActualResult)throws->Self {
        guard (0..<30).contains(revision),result.matches(input,baseline:baseline) else {throw CompanyConnectionError.invalidPrice};let id=baseline.scenario.scenarioId
        if let previous,previous.accountID==accountID,previous.scenarioID==id,previous.payload.expectedRevision==revision,previous.payload.snapshot==input,previous.result==result{return previous}
        return Self(accountID:accountID,scenarioID:id,payload:.init(expectedRevision:revision,idempotencyKey:UUID().uuidString,snapshot:input),result:result)
    }
    func accepts(_ row:CompanyActualRecord,identity:CompanyIdentity,caseID:String,baseline:CompanyActualBaseline)->Bool {scenarioID==baseline.scenario.scenarioId&&row.matches(identity,caseID:caseID,baseline:baseline)&&row.memberId==identity.memberId&&row.revision==payload.expectedRevision+1&&row.inputs==payload.snapshot&&row.result==result}
}

enum CompanyActualDocumentKind:String,Codable,CaseIterable,Identifiable,Sendable {
    case invoice="INVOICE",contract="CONTRACT",timesheet="TIMESHEET",acceptanceAct="ACCEPTANCE_ACT",paymentRecord="PAYMENT_RECORD",other="OTHER"
    var id:String {rawValue}
    var title:String {switch self {case .invoice:"Счёт";case .contract:"Договор";case .timesheet:"Табель трудозатрат";case .acceptanceAct:"Акт выполненных работ";case .paymentRecord:"Платёжный документ";case .other:"Прочее"}}
}
enum CompanyActualEvidenceRow:Equatable,Identifiable,Sendable {
    case planned(CompanyActualRow),unplanned(CompanyActualExtra)
    var kind:String {switch self {case .planned:"PLANNED";case .unplanned:"UNPLANNED"}}
    var ordinal:Int {switch self {case .planned(let l):l.ordinal;case .unplanned(let l):l.ordinal}}
    var title:String {switch self {case .planned(let l):l.title;case .unplanned(let l):l.title}}
    var amount:String? {switch self {case .planned(let l):l.actualAmountRub;case .unplanned(let l):l.actualAmountRub}}
    var id:String {kind+":"+String(ordinal)}
    var label:String {(kind=="PLANNED" ? "Плановая" : "Внеплановая")+" · \(ordinal). \(title) · \(amount ?? "—") ₽"}
    static func rows(_ snapshot:CompanyActualRecord)->[Self] {snapshot.result.lines.filter{$0.status=="USER_REPORTED_ACTUAL" && $0.actualAmountRub != nil}.map{.planned($0)}+snapshot.result.unplannedCosts.map{.unplanned($0)}}
    fileprivate func object()throws->[String:Any] {
        let encoder=JSONEncoder();encoder.keyEncodingStrategy = .convertToSnakeCase
        let bytes:Data
        switch self {case .planned(let l):bytes=try encoder.encode(l);case .unplanned(let l):bytes=try encoder.encode(l)}
        guard let obj=try JSONSerialization.jsonObject(with:bytes) as? [String:Any] else {throw CompanyConnectionError.invalidArtifact};return obj
    }
}
struct CompanyActualEvidenceTarget:Sendable {
    let baseline:CompanyActualBaseline;let snapshot:CompanyActualRecord;let row:CompanyActualEvidenceRow
    func digest()throws->String {
        let base=try baseline.digest()
        guard snapshot.scope.baselineSha256==base,snapshot.scope.scenarioId==baseline.scenario.scenarioId,snapshot.scope.scenarioRevision==baseline.scenario.revision,snapshot.result.matches(snapshot.inputs,baseline:baseline),CompanyActualEvidenceRow.rows(snapshot).contains(row) else {throw CompanyConnectionError.invalidArtifact}
        let object:[String:Any]=["scenario_id":baseline.scenario.scenarioId,"scenario_revision":baseline.scenario.revision,"baseline_sha256":base,"snapshot_id":snapshot.snapshotId,"snapshot_revision":snapshot.revision,"as_of":snapshot.inputs.asOf,"row_kind":row.kind,"line":try row.object()]
        return CompanyArtifactBytes.digest(Data(try CompanyActualBaseline.canonical(object).utf8))
    }
    func matches(_ identity:CompanyIdentity,caseID:String)->Bool {snapshot.matches(identity,caseID:caseID,baseline:baseline)&&CompanyActualEvidenceRow.rows(snapshot).contains(row)&&(try? digest()) != nil}
}
struct CompanyActualSampleRef: Codable, Equatable, Sendable {
    let caseId:String;let scenarioId:String;let snapshotId:String;let rowKind:String;let ordinal:Int;let lineSha256:String
}
struct CompanyActualSample: Codable, Equatable, Identifiable, Sendable {
    let sourcePlatform:String;let externalId:String;let caseId:String;let scenarioId:String;let scenarioRevision:Int;let baselineSha256:String;let snapshotId:String;let snapshotRevision:Int;let rowKind:String;let ordinal:Int;let lineSha256:String;let asOf:String;let title:String;let unit:String;let reportedQuantity:String;let reportedRateRub:String;let reportedAmountRub:String;let origin:String;let actualAmountVerified:Bool
    var id:String {caseId}
    var reference:CompanyActualSampleRef {.init(caseId:caseId,scenarioId:scenarioId,snapshotId:snapshotId,rowKind:rowKind,ordinal:ordinal,lineSha256:lineSha256)}
}
struct CompanyActualSampleSelection: Equatable, Sendable {
    let category:CompanyCostCategory;let sample:CompanyActualSample
    static func make(identity:CompanyIdentity,item:CompanyCase,target:CompanyActualEvidenceTarget,latestSnapshotID:String)throws->Self {
        guard identity.legalAccepted,["owner","admin","analyst"].contains(identity.role),target.snapshot.id==latestSnapshotID,target.matches(identity,caseID:item.caseId) else {throw CompanyConnectionError.invalidPrice}
        let category:CompanyCostCategory,unit:String,quantity:String,rate:String
        switch target.row {
        case .planned(let l):guard let q=l.actualQuantity,let r=l.actualRateRub else {throw CompanyConnectionError.invalidPrice};category=l.category;unit=l.unit;quantity=q;rate=r
        case .unplanned(let l):category=l.category;unit=l.unit;quantity=l.quantity;rate=l.rateRub
        }
        let platform=item.sourcePlatform ?? "eis"
        guard [.labor,.direct,.overhead].contains(category),let q=CompanyPriceInput.decimal(quantity),q>0,let amount=target.row.amount,let id=item.externalId ?? item.registryNumber,!id.isEmpty,["eis","workspace","b2bcenter"].contains(platform) else {throw CompanyConnectionError.invalidPrice}
        let s=target.snapshot
        return .init(category:category,sample:.init(sourcePlatform:platform,externalId:id,caseId:item.caseId,scenarioId:s.scope.scenarioId,scenarioRevision:s.scope.scenarioRevision,baselineSha256:s.scope.baselineSha256,snapshotId:s.id,snapshotRevision:s.revision,rowKind:target.row.kind,ordinal:target.row.ordinal,lineSha256:try target.digest(),asOf:s.inputs.asOf,title:target.row.title,unit:unit,reportedQuantity:quantity,reportedRateRub:rate,reportedAmountRub:amount,origin:"USER_REPORTED_UNVERIFIED",actualAmountVerified:false))
    }
}
struct CompanyActualSampleInput: Codable, Equatable, Sendable {
    let category:CompanyCostCategory;let title:String;let unit:String;let samples:[CompanyActualSampleRef]
    let confirmComparableReportedRows:Bool;let confirmOneCumulativeRowPerCase:Bool
    static func make(_ selections:[CompanyActualSampleSelection],comparable:Bool,distinct:Bool)throws->Self {
        guard let first=selections.first,selections.count<=20,comparable,distinct,Set(selections.map{$0.sample.caseId}).count==selections.count,Set(selections.map{$0.sample.sourcePlatform+"|"+$0.sample.externalId}).count==selections.count,selections.allSatisfy({$0.category==first.category && $0.sample.title==first.sample.title && $0.sample.unit==first.sample.unit}) else {throw CompanyConnectionError.invalidPrice}
        return .init(category:first.category,title:first.sample.title,unit:first.sample.unit,samples:selections.map{$0.sample.reference},confirmComparableReportedRows:comparable,confirmOneCumulativeRowPerCase:distinct)
    }
}
struct CompanyActualSampleDistribution: Codable, Equatable, Sendable {
    let minimum:String;let median:String;let maximum:String
    func matches(_ values:[String],digits:Int)->Bool {
        let nums=values.compactMap(CompanyPriceInput.decimal).sorted()
        guard !nums.isEmpty,nums.count==values.count else{return false}
        var midpoint=(nums[(nums.count-1)/2]+nums[nums.count/2])/2,rounded=Decimal()
        NSDecimalRound(&rounded,&midpoint,digits,.plain)
        return CompanyActualAccumulator.matches(minimum,nums.first,digits:digits)&&CompanyActualAccumulator.matches(median,rounded,digits:digits)&&CompanyActualAccumulator.matches(maximum,nums.last,digits:digits)
    }
}
struct CompanyActualSamplePreview: Codable, Sendable {
    let schema:String;let customerId:String;let category:CompanyCostCategory;let title:String;let unit:String;let currency:String;let distinctCaseCount:Int;let samples:[CompanyActualSample]
    let reportedQuantityDistribution:CompanyActualSampleDistribution;let reportedUnitRateDistributionRub:CompanyActualSampleDistribution;let reportedAmountDistributionRub:CompanyActualSampleDistribution
    let basis:String;let smallSampleWarning:Bool;let comparabilityIndependentlyVerified:Bool;let actualAmountsIndependentlyVerified:Bool;let contractExecutionVerified:Bool;let approvedNorm:Bool;let recommendedRate:String?;let inputsStored:Bool;let externalSubmissionAllowed:Bool
    func matches(_ identity:CompanyIdentity,input:CompanyActualSampleInput,selections:[CompanyActualSampleSelection])->Bool {
        guard (try? CompanyActualSampleInput.make(selections,comparable:input.confirmComparableReportedRows,distinct:input.confirmOneCumulativeRowPerCase))==input,schema=="company_actual_descriptive_sample_v1",customerId==identity.customerId,category==input.category,title==input.title,unit==input.unit,currency=="RUB",distinctCaseCount==selections.count,samples==selections.map(\.sample),basis=="EXPLICIT_ONE_CUMULATIVE_REPORTED_ROW_PER_DISTINCT_CASE",smallSampleWarning==(samples.count<5),!comparabilityIndependentlyVerified,!actualAmountsIndependentlyVerified,!contractExecutionVerified,!approvedNorm,recommendedRate==nil,!inputsStored,!externalSubmissionAllowed else{return false}
        return reportedQuantityDistribution.matches(samples.map(\.reportedQuantity),digits:4)&&reportedUnitRateDistributionRub.matches(samples.map(\.reportedRateRub),digits:3)&&reportedAmountDistributionRub.matches(samples.map(\.reportedAmountRub),digits:3)
    }
}

struct CompanyNormProposal: Codable, Equatable, Sendable {
    let sample:CompanyActualSampleInput
    let normQuantity:String;let normRateRub:String;let rationale:String;let confirmReportedSourceLimits:Bool
    static func make(selections:[CompanyActualSampleSelection],comparable:Bool,distinct:Bool,quantity:String,rate:String,note:String,limits:Bool)throws->Self {
        let p=Self(sample:try .make(selections,comparable:comparable,distinct:distinct),normQuantity:quantity.trimmingCharacters(in:.whitespacesAndNewlines).replacingOccurrences(of:",",with:"."),normRateRub:rate.trimmingCharacters(in:.whitespacesAndNewlines).replacingOccurrences(of:",",with:"."),rationale:note.trimmingCharacters(in:.whitespacesAndNewlines),confirmReportedSourceLimits:limits)
        guard p.valid else {throw CompanyConnectionError.invalidPrice};return p
    }
    var valid:Bool {
        confirmReportedSourceLimits && normQuantity.range(of:#"^[0-9]{1,9}(\.[0-9]{1,4})?$"#,options:.regularExpression) != nil && (CompanyPriceInput.decimal(normQuantity) ?? 0)>0 && normRateRub.range(of:#"^[0-9]{1,12}(\.[0-9]{1,2})?$"#,options:.regularExpression) != nil && (10...2000).contains(rationale.unicodeScalars.count)
    }
}
enum CompanyNormDigest {
    static func object<T:Encodable>(_ value:T)throws->[String:Any] {
        let e=JSONEncoder();e.keyEncodingStrategy = .convertToSnakeCase
        guard let o=try JSONSerialization.jsonObject(with:e.encode(value)) as? [String:Any] else {throw CompanyConnectionError.invalidResponse};return o
    }
    static func hash(_ value:[String:Any])throws->String {CompanyArtifactBytes.digest(Data(try CompanyActualBaseline.canonical(value).utf8))}
    static func observation(_ value:CompanyActualSamplePreview)throws->[String:Any] {
        var o=try object(value);o["recommended_rate"]=(value.recommendedRate as Any?) ?? NSNull();return o
    }
    static func preview(identity:CompanyIdentity,key:String,revision:Int,proposal:CompanyNormProposal,observation:CompanyActualSamplePreview)throws->String {
        try hash(["schema":"company_cost_norm_preview_v1","customer_id":identity.customerId,"norm_key":key,"expected_revision":revision,"proposal":object(proposal),"sample_observation":self.observation(observation),"approved_norm":false,"automatically_applied":false,"inputs_stored":false,"external_submission_allowed":false])
    }
    static func stamp(_ s:String)->String? {
        let v=s.hasSuffix("Z") ? String(s.dropLast())+"+00:00":s
        return v.range(of:#"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{6})?\+00:00$"#,options:.regularExpression) != nil ? v:nil
    }
    static func isSHA(_ s:String)->Bool {s.range(of:#"^[0-9a-f]{64}$"#,options:.regularExpression) != nil}
}
struct CompanyNormPreview: Decodable,Sendable {
    let schema:String;let customerId:String;let normKey:String;let expectedRevision:Int;let proposal:CompanyNormProposal;let sampleObservation:CompanyActualSamplePreview;let approvedNorm:Bool;let automaticallyApplied:Bool;let inputsStored:Bool;let externalSubmissionAllowed:Bool;let previewSha256:String
    func matches(_ identity:CompanyIdentity,proposal p:CompanyNormProposal,selections:[CompanyActualSampleSelection])->Bool {
        schema=="company_cost_norm_preview_v1" && customerId==identity.customerId && CompanyNormDigest.isSHA(normKey) && (0...100).contains(expectedRevision) && proposal==p && p.valid && !approvedNorm && !automaticallyApplied && !inputsStored && !externalSubmissionAllowed && sampleObservation.matches(identity,input:p.sample,selections:selections) && previewSha256==(try? CompanyNormDigest.preview(identity:identity,key:normKey,revision:expectedRevision,proposal:p,observation:sampleObservation))
    }
}
struct CompanyNormApproval: Codable,Equatable,Sendable {
    let proposal:CompanyNormProposal;let previewSha256:String;let expectedRevision:Int;let idempotencyKey:String;let confirmInternalApproval:Bool
}
struct CompanyNormWithdrawal: Codable,Equatable,Sendable {
    let expectedRevision:Int;let idempotencyKey:String;let rationale:String;let confirmWithdrawal:Bool
}
struct CompanyNormRecord: Decodable,Identifiable,Sendable {
    let schema:String;let customerId:String;let normId:String;let normKey:String;let revision:Int;let action:String;let memberId:String;let createdAt:String;let recordSha256:String;let inputs:Inputs;let result:Result;let externalSubmissionAllowed:Bool;let automaticallyApplied:Bool
    var id:String {normId}
    struct Inputs:Codable,Sendable {
        let expectedRevision:Int;let idempotencyKey:String;let proposal:CompanyNormProposal?;let previewSha256:String?;let confirmInternalApproval:Bool?;let rationale:String?;let confirmWithdrawal:Bool?
        var approval:CompanyNormApproval? {guard let proposal,let previewSha256,let confirmInternalApproval else{return nil};return .init(proposal:proposal,previewSha256:previewSha256,expectedRevision:expectedRevision,idempotencyKey:idempotencyKey,confirmInternalApproval:confirmInternalApproval)}
        var withdrawal:CompanyNormWithdrawal? {guard let rationale,let confirmWithdrawal else{return nil};return .init(expectedRevision:expectedRevision,idempotencyKey:idempotencyKey,rationale:rationale,confirmWithdrawal:confirmWithdrawal)}
    }
    struct Result: Codable,Sendable {
        let category:CompanyCostCategory;let title:String;let unit:String;let currency:String;let normQuantity:String?;let normRateRub:String?;let rationale:String;let sampleObservation:CompanyActualSamplePreview?;let previewSha256:String?;let origin:String?;let approvedNorm:Bool;let actualAmountsIndependentlyVerified:Bool?;let automaticallyApplied:Bool;let externalSubmissionAllowed:Bool;let withdrawnNormId:String?;let withdrawnRecordSha256:String?
    }
    func matches(_ identity:CompanyIdentity)->Bool {
        guard schema=="company_cost_norm_version_v1",customerId==identity.customerId,!normId.isEmpty,!memberId.isEmpty,CompanyNormDigest.isSHA(normKey),(1...100).contains(revision),inputs.expectedRevision==revision-1,(8...128).contains(inputs.idempotencyKey.count),!externalSubmissionAllowed,!automaticallyApplied,!result.automaticallyApplied,!result.externalSubmissionAllowed,result.currency=="RUB",[.labor,.direct,.overhead].contains(result.category),!result.title.isEmpty,!result.unit.isEmpty,let stamp=CompanyNormDigest.stamp(createdAt) else{return false}
        switch action {
        case "APPROVED":
            guard let a=inputs.approval,inputs.rationale==nil,inputs.confirmWithdrawal==nil,a.confirmInternalApproval,a.proposal.valid,let o=result.sampleObservation,result.approvedNorm,result.actualAmountsIndependentlyVerified==false,result.origin=="EXPLICIT_INTERNAL_MANAGER_APPROVAL",result.previewSha256==a.previewSha256,result.normQuantity==a.proposal.normQuantity,result.normRateRub==a.proposal.normRateRub,result.rationale==a.proposal.rationale,result.category==a.proposal.sample.category,result.title==a.proposal.sample.title,result.unit==a.proposal.sample.unit,result.withdrawnNormId==nil,result.withdrawnRecordSha256==nil,(1...20).contains(o.samples.count),o.samples.allSatisfy({$0.origin=="USER_REPORTED_UNVERIFIED" && !$0.actualAmountVerified && CompanyNormDigest.isSHA($0.lineSha256) && (CompanyPriceInput.decimal($0.reportedQuantity) ?? 0)>0}),o.matches(identity,input:a.proposal.sample,selections:o.samples.map{.init(category:result.category,sample:$0)}),a.previewSha256==(try? CompanyNormDigest.preview(identity:identity,key:normKey,revision:inputs.expectedRevision,proposal:a.proposal,observation:o)) else{return false}
        case "WITHDRAWN":
            guard let w=inputs.withdrawal,inputs.proposal==nil,inputs.previewSha256==nil,inputs.confirmInternalApproval==nil,w.confirmWithdrawal,w.expectedRevision>=1,!result.approvedNorm,result.rationale==w.rationale,result.normQuantity==nil,result.normRateRub==nil,result.sampleObservation==nil,result.previewSha256==nil,result.origin==nil,result.actualAmountsIndependentlyVerified==nil,let old=result.withdrawnNormId,!old.isEmpty,let sha=result.withdrawnRecordSha256,CompanyNormDigest.isSHA(sha) else{return false}
        default:return false
        }
        do {
            var x=try CompanyNormDigest.object(result)
            if let o=result.sampleObservation {x["sample_observation"]=try CompanyNormDigest.observation(o)}
            let p=try CompanyNormDigest.object(inputs)
            return recordSha256 == (try CompanyNormDigest.hash(["norm_id":normId,"created_at":stamp,"tenant_id":identity.tenantId,"member_id":memberId,"norm_key":normKey,"revision":revision,"action":action,"idempotency_key":inputs.idempotencyKey,"inputs":p,"result":x]))
        }catch{return false}
    }
}
struct CompanyNormPage:Decodable,Sendable {
    let customerId:String;let normKey:String?;let items:[CompanyNormRecord];let hasMore:Bool
    func matches(_ identity:CompanyIdentity,key:String?)->Bool {
        guard customerId==identity.customerId,normKey==key,items.count<=10,items.allSatisfy({$0.matches(identity)}) else{return false}
        if let key{return items.allSatisfy{$0.normKey==key} && zip(items,items.dropFirst()).allSatisfy{$0.0.revision==$0.1.revision+1}}
        return Set(items.map(\.normKey)).count==items.count
    }
}

// Preserve explicit JSON nulls and integer types for Python-compatible SHA-256.
indirect enum CompanyHistoricalJSON: Decodable, Equatable, Sendable {
    case object([String:Self]), array([Self]), text(String), integer(Int), boolean(Bool), null
    init(from decoder:Decoder)throws {
        let c=try decoder.singleValueContainer()
        if c.decodeNil(){self = .null}
        else if let v=try? c.decode(Bool.self){self = .boolean(v)}
        else if let v=try? c.decode(Int.self){self = .integer(v)}
        else if let v=try? c.decode(String.self){self = .text(v)}
        else if let v=try? c.decode([Self].self){self = .array(v)}
        else if let v=try? c.decode([String:Self].self){self = .object(v)}
        else{throw CompanyConnectionError.invalidResponse}
    }
    var value:Any {
        switch self {
        case .object(let x):x.mapValues{ $0.value }
        case .array(let x):x.map{ $0.value }
        case .text(let x):x
        case .integer(let x):x
        case .boolean(let x):x
        case .null:NSNull()
        }
    }
    var fields:[String:Self]? {if case .object(let x)=self{return x};return nil}
    var elements:[Self]? {if case .array(let x)=self{return x};return nil}
    var text:String? {if case .text(let x)=self{return x};return nil}
    var display:String {switch self{case .text(let x):x;case .integer(let x):String(x);default:"—"}}
    func typed<T:Decodable>(_ type:T.Type)throws->T {
        try TenderAgentJSON.makeDecoder().decode(type,from:JSONSerialization.data(withJSONObject:value,options:[.fragmentsAllowed]))
    }
    func digest()throws->String {CompanyArtifactBytes.digest(Data(try CompanyActualBaseline.canonical(value).utf8))}
}
struct CompanyHistoricalDimension:Decodable,Sendable,Identifiable {
    let dimension:String;let sourceValue:CompanyHistoricalJSON;let unit:String;let constraintKind:String;let reviewedInterpretation:String;let sourceQuote:String;let sourceLineOrdinal:Int;let sourceLineSha256:String
    var id:String {dimension}
}
struct CompanyHistoricalDifference:Decodable,Sendable,Identifiable {
    let dimension:String;let state:String;let reference:CompanyHistoricalDimension?;let candidate:CompanyHistoricalDimension?
    var id:String {dimension}
    var label:String {switch state{case "SAME_REPORTED_DIMENSION":"Совпадает параметр";case "DIFFERENT_REPORTED_DIMENSION":"Различается";default:"Недостаточно данных"}}
}
struct CompanyHistoricalRecord:Decodable,Sendable,Identifiable {
    struct Prices:Decodable,Sendable {let minimum:String?;let median:String?;let maximum:String?}
    let registryNumber:String;let subject:String;let totalOffers:Int;let admittedOffers:Int;let rejectedOffers:Int
    let admittedProtocolPricesRub:Prices;let subRubleOfferObserved:Bool;let winnerOfferRub:String?
    let sourceScopeStateRelativeToAksay:String;let sourceScopeReasonRelativeToAksay:String;let scopeAnchors:[String];let provenance:[String:String];let scopeDimensions:[CompanyHistoricalDimension]
    let comparisonState:String?;let scopeComparison:[CompanyHistoricalDifference]?
    var id:String {registryNumber}
    var stateLabel:String {
        switch comparisonState ?? sourceScopeStateRelativeToAksay {
        case "REFERENCE_ONLY":"Базовая закупка"
        case "BASELINE_ONLY":"Исходная корзина"
        case "RELATED_SCOPE_REQUIRES_NORMALIZATION":"Требуется нормализация"
        case "NOT_COMPARABLE_REGULATED_OFFICIAL_SITE":"Иные регуляторные требования"
        case "NOT_COMPARABLE_CUSTOM_CMS":"Иная CMS"
        case "NOT_COMPARABLE_COMPOUND_SUPPORT":"Комплексное сопровождение"
        default:"Эквивалентность пары не проверена"
        }
    }
}
struct CompanyHistoricalSelection:Encodable,Equatable,Sendable {
    let referenceRegistryNumber:String;let selectedRegistryNumbers:[String];let confirmReviewSourceScope:Bool
    func valid(in catalog:CompanyHistoricalCatalog)->Bool {
        confirmReviewSourceScope && (1...6).contains(selectedRegistryNumbers.count) && Set(selectedRegistryNumbers).count==selectedRegistryNumbers.count && selectedRegistryNumbers.contains(referenceRegistryNumber) && selectedRegistryNumbers.allSatisfy{ id in catalog.records.contains{$0.id==id} }
    }
}
struct CompanyHistoricalCatalog:Sendable {
    static let aksay="0158300034526000388"
    static let cohort="65038a3e607bb2e2e51b1dffc05ee10c36a00b59e8817141a4c6be3146a9e963"
    static let workload="fefb77d99df0999e626a916d3edc58a942a75cec894c7c56da309f1f6b0ce74f"
    // Exact reviewed projection for this fixed six-procedure archive; changes require review.
    static let recordsDigest="b7f0c04708e41cd4385a14069c294ba2a207f7f6ab75372451ce52e649fc6f06"
    let records:[CompanyHistoricalRecord]
    fileprivate let rawRecords:[CompanyHistoricalJSON]
    fileprivate let context:[String:CompanyHistoricalJSON]
    static func context(identity:CompanyIdentity,item:CompanyCase)throws->[String:CompanyHistoricalJSON] {
        guard identity.legalAccepted,["owner","admin","analyst"].contains(identity.role),let external=item.externalId ?? item.registryNumber else{throw CompanyConnectionError.identityMismatch}
        return ["customer_id":.text(identity.customerId),"case_id":.text(item.caseId),"target_source_platform":.text(item.sourcePlatform ?? "eis"),"target_external_id":.text(external),"target_scope_verified":.boolean(false),"cohort_receipt_sha256":.text(cohort),"workload_receipt_sha256":.text(workload),"signed_contract_prices_verified_count":.integer(0),"current_market_price":.null,"recommendation":.null,"external_submission_allowed":.boolean(false)]
    }
    static func verified(_ raw:CompanyHistoricalJSON,identity:CompanyIdentity,item:CompanyCase)throws->Self {
        let context=try context(identity:identity,item:item)
        guard var actual=raw.fields,let sha=actual.removeValue(forKey:"catalog_sha256")?.text,sha == (try CompanyHistoricalJSON.object(actual).digest()),let records=actual["records"],let list=records.elements,list.count==6,try records.digest()==recordsDigest else{throw CompanyConnectionError.identityMismatch}
        var expected=context;expected["schema"] = .text("company_historical_comparable_catalog_v1");expected["archive_scope"] = .text("SIX_REVIEWED_EIS_WEBSITE_PROCEDURES");expected["records"]=records
        guard actual==expected else{throw CompanyConnectionError.identityMismatch}
        return .init(records:try records.typed([CompanyHistoricalRecord].self),rawRecords:list,context:context)
    }
    func matches(identity:CompanyIdentity,item:CompanyCase)->Bool {(try? Self.context(identity:identity,item:item))==context}
}
struct CompanyHistoricalPreview:Sendable {
    let observations:[CompanyHistoricalRecord];let targetReferenceIdentityMatches:Bool;let pricedProcedures:Int
    private static func differences(_ a:CompanyHistoricalJSON,_ b:CompanyHistoricalJSON)throws->[CompanyHistoricalJSON] {
        guard let x=a.fields?["scope_dimensions"]?.elements,let y=b.fields?["scope_dimensions"]?.elements else{throw CompanyConnectionError.invalidResponse}
        if x.isEmpty || y.isEmpty{return []}
        func index(_ rows:[CompanyHistoricalJSON])throws->[String:CompanyHistoricalJSON] {
            var result=[String:CompanyHistoricalJSON]()
            for row in rows {guard let key=row.fields?["dimension"]?.text,result[key]==nil else{throw CompanyConnectionError.invalidResponse};result[key]=row}
            return result
        }
        let left=try index(x),right=try index(y)
        return Set(left.keys).union(right.keys).sorted().map{key in
            let ref=left[key],candidate=right[key]
            let state:String
            if let ref,let candidate {state=["source_value","unit","constraint_kind"].allSatisfy{ref.fields?[$0]==candidate.fields?[$0]} ? "SAME_REPORTED_DIMENSION":"DIFFERENT_REPORTED_DIMENSION"}
            else{state="UNKNOWN_ON_ONE_SIDE"}
            return .object(["dimension":.text(key),"state":.text(state),"reference":ref ?? .null,"candidate":candidate ?? .null])
        }
    }
    static func verified(_ raw:CompanyHistoricalJSON,identity:CompanyIdentity,item:CompanyCase,catalog:CompanyHistoricalCatalog,selection:CompanyHistoricalSelection)throws->Self {
        guard catalog.matches(identity:identity,item:item),selection.valid(in:catalog),var actual=raw.fields,let sha=actual.removeValue(forKey:"preview_sha256")?.text,sha == (try CompanyHistoricalJSON.object(actual).digest()) else{throw CompanyConnectionError.identityMismatch}
        let reference=selection.referenceRegistryNumber
        let index=Dictionary(uniqueKeysWithValues:zip(catalog.records.map(\.id),catalog.rawRecords))
        guard let base=index[reference] else{throw CompanyConnectionError.invalidResponse}
        var observations=[CompanyHistoricalJSON]();var priced=0
        for id in selection.selectedRegistryNumbers {
            guard let row=index[id],var fields=row.fields,let sourceState=fields["source_scope_state_relative_to_aksay"],let median=fields["admitted_protocol_prices_rub"]?.fields?["median"] else{throw CompanyConnectionError.invalidResponse}
            if median != .null{priced+=1}
            fields["comparison_state"]=id==reference ? .text("REFERENCE_ONLY") : reference==CompanyHistoricalCatalog.aksay ? sourceState : .text("PAIRWISE_SCOPE_NOT_REVIEWED")
            fields["scope_comparison"] = .array(id==reference ? [] : try differences(base,row))
            fields["accepted_for_cross_procurement_normalization"] = .boolean(false)
            observations.append(.object(fields))
        }
        let same=(item.sourcePlatform ?? "eis")=="eis" && (item.externalId ?? item.registryNumber)==reference
        var expected=catalog.context
        let extra:[String:CompanyHistoricalJSON]=["schema":.text("company_historical_comparable_preview_v1"),"reference_registry_number":.text(reference),"target_reference_identity_matches":.boolean(same),"selected_distinct_procurements":.integer(observations.count),"observations":.array(observations),"admitted_price_procedures_count":.integer(priced),"reference_procurements_count":.integer(1),"additional_equivalent_procurements":.integer(0),"normalization_state":.text("INSUFFICIENT_VERIFIED_EQUIVALENT_SCOPE_AND_QUANTITY"),"normalized_admitted_offer_range_rub":.null,"normalized_signed_contract_range_rub":.null,"cross_procurement_price_rub":.null,"win_probability":.null,"inputs_stored":.boolean(false)]
        expected.merge(extra){_,new in new}
        guard actual==expected else{throw CompanyConnectionError.identityMismatch}
        return .init(observations:try CompanyHistoricalJSON.array(observations).typed([CompanyHistoricalRecord].self),targetReferenceIdentityMatches:same,pricedProcedures:priced)
    }
}

struct CompanyActualEvidenceScope:Decodable,Equatable,Sendable {
    let base:CompanyActualScope;let snapshotId:String;let snapshotRevision:Int;let asOf:String;let rowKind:String;let lineOrdinal:Int;let lineTitle:String;let actualAmountRub:String;let lineSha256:String
    private enum CodingKeys:String,CodingKey {case snapshotId,snapshotRevision,asOf,rowKind,lineOrdinal,lineTitle,actualAmountRub,lineSha256}
    init(from decoder:Decoder)throws {base=try CompanyActualScope(from:decoder);let c=try decoder.container(keyedBy:CodingKeys.self);snapshotId=try c.decode(String.self,forKey:.snapshotId);snapshotRevision=try c.decode(Int.self,forKey:.snapshotRevision);asOf=try c.decode(String.self,forKey:.asOf);rowKind=try c.decode(String.self,forKey:.rowKind);lineOrdinal=try c.decode(Int.self,forKey:.lineOrdinal);lineTitle=try c.decode(String.self,forKey:.lineTitle);actualAmountRub=try c.decode(String.self,forKey:.actualAmountRub);lineSha256=try c.decode(String.self,forKey:.lineSha256)}
    func matches(_ identity:CompanyIdentity,caseID:String,target:CompanyActualEvidenceTarget)->Bool {target.matches(identity,caseID:caseID)&&base==target.snapshot.scope&&snapshotId==target.snapshot.snapshotId&&snapshotRevision==target.snapshot.revision&&asOf==target.snapshot.inputs.asOf&&rowKind==target.row.kind&&lineOrdinal==target.row.ordinal&&lineTitle==target.row.title&&actualAmountRub==target.row.amount&&lineSha256==(try? target.digest())}
}
struct CompanyActualEvidence:Decodable,Equatable,Sendable {
    let scope:CompanyActualEvidenceScope;let evidenceId:String;let memberId:String;let documentKind:CompanyActualDocumentKind;let formatHint:String;let inspection:CompanyCostInspection;let origin:String;let storedBytesReverified:Bool;let documentOriginVerified:Bool;let actualAmountVerified:Bool;let paymentVerified:Bool;let contractExecutionVerified:Bool
    private enum CodingKeys:String,CodingKey {case evidenceId,memberId,documentKind,formatHint,inspection,origin,storedBytesReverified,documentOriginVerified,actualAmountVerified,paymentVerified,contractExecutionVerified}
    init(from decoder:Decoder)throws {scope=try CompanyActualEvidenceScope(from:decoder);let c=try decoder.container(keyedBy:CodingKeys.self);evidenceId=try c.decode(String.self,forKey:.evidenceId);memberId=try c.decode(String.self,forKey:.memberId);documentKind=try c.decode(CompanyActualDocumentKind.self,forKey:.documentKind);formatHint=try c.decode(String.self,forKey:.formatHint);inspection=try c.decode(CompanyCostInspection.self,forKey:.inspection);origin=try c.decode(String.self,forKey:.origin);storedBytesReverified=try c.decode(Bool.self,forKey:.storedBytesReverified);documentOriginVerified=try c.decode(Bool.self,forKey:.documentOriginVerified);actualAmountVerified=try c.decode(Bool.self,forKey:.actualAmountVerified);paymentVerified=try c.decode(Bool.self,forKey:.paymentVerified);contractExecutionVerified=try c.decode(Bool.self,forKey:.contractExecutionVerified)}
    func matches(_ identity:CompanyIdentity,caseID:String,target:CompanyActualEvidenceTarget)->Bool {scope.matches(identity,caseID:caseID,target:target)&&UUID(uuidString:evidenceId) != nil && !memberId.isEmpty&&inspection.valid&&formatHint==inspection.formatHint&&origin=="USER_SUPPLIED_UNATTESTED"&&storedBytesReverified && !documentOriginVerified && !actualAmountVerified && !paymentVerified && !contractExecutionVerified}
    func accepts(_ bytes:CompanyArtifactBytes)->Bool {formatHint==bytes.format&&inspection.sizeBytes==bytes.data.count&&inspection.sha256==bytes.sha256}
    var filename:String {"actual-\(inspection.sha256.prefix(16)).\(formatHint)"}
}
struct CompanyActualEvidenceBinding:Decodable,Sendable {
    let scope:CompanyActualEvidenceScope;let evidence:CompanyActualEvidence?
    private enum CodingKeys:String,CodingKey {case evidence}
    init(from decoder:Decoder)throws {scope=try CompanyActualEvidenceScope(from:decoder);let c=try decoder.container(keyedBy:CodingKeys.self);guard c.contains(.evidence) else {throw CompanyConnectionError.invalidResponse};evidence=try c.decodeIfPresent(CompanyActualEvidence.self,forKey:.evidence)}
    func matches(_ identity:CompanyIdentity,caseID:String,target:CompanyActualEvidenceTarget)->Bool {scope.matches(identity,caseID:caseID,target:target)&&(evidence.map{$0.scope==scope&&$0.matches(identity,caseID:caseID,target:target)} ?? true)}
}

struct CompanyPriceHistory: Decodable, Sendable {
    let customerId: String
    let caseId: String
    let items: [CompanyPriceRecord]
    let hasMore: Bool
    let externalSubmissionAllowed: Bool
    func matches(_ identity: CompanyIdentity, caseID: String) -> Bool {
        customerId == identity.customerId && caseId == caseID && !hasMore && !externalSubmissionAllowed && items.count <= 30 && Set(items.map(\.id)).count == items.count && items.enumerated().allSatisfy { $0.element.matches(identity, caseID: caseID) && $0.element.revision == items.count - $0.offset }
    }
}

struct CompanyPriceSavePayload: Codable, Equatable, Sendable {
    let expectedRevision: Int
    let idempotencyKey: String
    let scenario: CompanyPriceInput
}

struct CompanyPriceAttempt: Equatable, Sendable {
    let accountID: String
    let caseID: String
    let payload: CompanyPriceSavePayload
    let preview: CompanyPriceResult
    let itemized: CompanyItemizedProjection?
    static func prepare(previous: Self?, accountID: String, caseID: String, revision: Int, input: CompanyPriceInput, result: CompanyPriceResult, itemized: CompanyItemizedProjection? = nil) throws -> Self {
        guard (0..<30).contains(revision), result.matches(input), itemized.map({ $0.matches(input) }) ?? true else { throw CompanyConnectionError.invalidPrice }
        if let previous, previous.accountID == accountID, previous.caseID == caseID, previous.payload.expectedRevision == revision, previous.payload.scenario == input, previous.preview == result, previous.itemized == itemized { return previous }
        return Self(accountID:accountID,caseID:caseID,payload:.init(expectedRevision:revision,idempotencyKey:UUID().uuidString,scenario:input),preview:result,itemized:itemized)
    }
    func accepts(_ row: CompanyPriceRecord, identity: CompanyIdentity) -> Bool {
        row.matches(identity,caseID:caseID) && row.memberId == identity.memberId && row.revision == payload.expectedRevision + 1 && row.inputs == payload.scenario && row.result == preview && row.itemizedEstimate == itemized
    }
}

struct CompanyEvidence: Decodable, Identifiable, Sendable {
    let bindingId: String
    let caseId: String
    let runId: String
    let profileVersion: Int
    let currentProfileVersion: Int?
    let profileState: String
    var id: String { bindingId }
}

struct CompanyEvidencePage: Decodable, Sendable {
    let items: [CompanyEvidence]
    let hasMore: Bool
}

enum CompanyConnectionError: LocalizedError {
    case invalidOrigin, invalidToken, identityMismatch, invalidResponse, http(Int), storage, invalidDecision, decisionUncertain, invalidLifecycle, lifecycleUncertain, invalidArtifact, invalidPrice, priceUncertain

    var errorDescription: String? {
        switch self {
        case .invalidOrigin: "Нужен доверенный HTTPS-адрес сервера без пути и параметров."
        case .invalidToken: "Требуется действующий токен компании saas_…"
        case .identityMismatch: "Компания или участник не совпадают. Доступ остановлен."
        case .invalidResponse: "Некорректный ответ сервера."
        case .http(401): "Токен истёк или отозван. Подключитесь повторно."
        case .http(402): "Доступ компании по текущему пакету завершён."
        case .http(403): "Доступ запрещён для этой роли или компании."
        case .http(428): "Подтвердите условия пилота в веб-кабинете."
        case .storage: "Не удалось сохранить подключения в Keychain."
        case .invalidDecision: "Укажите действие, обоснование и будущую дату отсрочки, если она нужна."
        case .invalidPrice: "Заполните явные расходы, ставки, цены и обоснование. Проверьте допущения."
        case .priceUncertain: "Ответ о сохранении не получен. Повторите тот же расчёт или проверьте историю."
        case .invalidArtifact: "Допустимы PDF, DOCX и XLSX до 2 МБ; проверка файла не пройдена."
        case .invalidLifecycle: "Проверьте допустимое состояние, обоснование, ссылку и дату события."
        case .lifecycleUncertain: "Ответ о записи не получен. Проверьте журнал или повторите ту же запись."
        case .decisionUncertain: "Ответ о сохранении не получен. Проверьте карточку или явно повторите то же решение."
        case .http(409): "Решение уже изменилось. Откройте обновлённую карточку и подтвердите заново."
        case let .http(code): "Сервер вернул HTTP \(code)."
        }
    }
}

final class CompanyNoRedirect: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest,
                    completionHandler: @escaping @Sendable (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}

struct CompanyAPIClient: Sendable {
    let baseURL: URL
    private let token: String
    private let session: URLSession

    static func validatedOrigin(_ input: String) throws -> URL {
        guard var parts = URLComponents(string: input.trimmingCharacters(in: .whitespacesAndNewlines)),
              parts.scheme?.lowercased() == "https", let host = parts.host, !host.isEmpty,
              parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil,
              parts.path == "" || parts.path == "/" else { throw CompanyConnectionError.invalidOrigin }
        parts.scheme = "https"
        parts.host = host.lowercased()
        parts.path = ""
        if parts.port == 443 { parts.port = nil }
        guard let result = parts.url else { throw CompanyConnectionError.invalidOrigin }
        return result
    }

    init(origin: String, token: String, session: URLSession? = nil) throws {
        baseURL = try Self.validatedOrigin(origin)
        guard token.hasPrefix("saas_"), token.count <= 160, token.count > 20,
              token.utf8.allSatisfy({ (65...90).contains($0) || (97...122).contains($0) || (48...57).contains($0) || $0 == 95 || $0 == 45 }) else {
            throw CompanyConnectionError.invalidToken
        }
        self.token = token
        let config = URLSessionConfiguration.ephemeral
        config.urlCache = nil
        config.httpCookieStorage = nil
        config.httpShouldSetCookies = false
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        self.session = session ?? URLSession(configuration: config, delegate: CompanyNoRedirect(), delegateQueue: nil)
    }

    init(connection: CompanyConnection, session: URLSession? = nil) throws {
        try self.init(origin: connection.baseURL.absoluteString, token: connection.token, session: session)
    }

    func identity() async throws -> CompanyIdentity { try await get("api/saas/me") }

    func verifiedIdentity(for expected: CompanyIdentity) async throws -> CompanyIdentity {
        let actual = try await identity()
        guard actual.matchesAccount(expected) else { throw CompanyConnectionError.identityMismatch }
        return actual
    }

    func portfolio(for identity: CompanyIdentity, offset: Int = 0) async throws -> CompanyPortfolioPage {
        let page: CompanyPortfolioPage = try await get("api/saas/company-portfolio/cases", query: [URLQueryItem(name: "offset", value: String(offset))])
        guard page.matchesCompany(identity) else { throw CompanyConnectionError.identityMismatch }
        return page
    }

    func inbox(for identity: CompanyIdentity, filter: CompanyInboxFilter, offset: Int = 0) async throws -> CompanyInboxPage {
        let page: CompanyInboxPage = try await get("api/saas/company-portfolio/manager-inbox", query: [
            URLQueryItem(name: "view", value: filter.rawValue), URLQueryItem(name: "offset", value: String(offset)), URLQueryItem(name: "limit", value: "50")])
        guard page.matches(identity, filter: filter, offset: offset) else { throw CompanyConnectionError.identityMismatch }
        return page
    }

    func evidence(caseId: String) async throws -> CompanyEvidencePage {
        guard UUID(uuidString: caseId) != nil else { throw CompanyConnectionError.invalidResponse }
        let page: CompanyEvidencePage = try await get("api/saas/company-portfolio/cases/\(caseId)/evidence")
        guard page.items.allSatisfy({ $0.caseId == caseId }) else { throw CompanyConnectionError.identityMismatch }
        return page
    }

    func recordDecision(_ attempt: CompanyDecisionAttempt, for identity: CompanyIdentity) async throws -> CompanyDecision {
        guard UUID(uuidString: attempt.caseID) != nil else { throw CompanyConnectionError.invalidResponse }
        guard identity.legalAccepted, ["owner", "admin"].contains(identity.role) else { throw CompanyConnectionError.http(403) }
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        let result: CompanyDecision = try await get("api/saas/company-portfolio/cases/\(attempt.caseID)/decisions",
                                                   method: "POST", body: encoder.encode(attempt.payload))
        guard attempt.accepts(result, memberID: identity.memberId) else { throw CompanyConnectionError.decisionUncertain }
        return result
    }

    func lifecycle(for item: CompanyCase, identity: CompanyIdentity) async throws -> CompanyLifecycleState {
        guard UUID(uuidString: item.caseId) != nil else { throw CompanyConnectionError.invalidResponse }
        let state: CompanyLifecycleState = try await get("api/saas/company-portfolio/cases/\(item.caseId)/lifecycle")
        guard state.customerId == identity.customerId, state.caseId == item.caseId else { throw CompanyConnectionError.identityMismatch }
        guard state.decisionRevision == item.revision else { throw CompanyConnectionError.http(409) }
        guard state.matches(identity, item: item) else { throw CompanyConnectionError.identityMismatch }
        return state
    }

    func lifecycleHistory(caseID: String, identity: CompanyIdentity) async throws -> CompanyLifecycleHistory {
        guard UUID(uuidString: caseID) != nil else { throw CompanyConnectionError.invalidResponse }
        let result: CompanyLifecycleHistory = try await get("api/saas/company-portfolio/cases/\(caseID)/lifecycle/history")
        guard result.matches(identity, caseID: caseID) else { throw CompanyConnectionError.identityMismatch }
        return result
    }

    func lifecycleMetrics(for identity: CompanyIdentity) async throws -> CompanyLifecycleMetrics {
        let result: CompanyLifecycleMetrics = try await get("api/saas/company-portfolio/lifecycle-metrics")
        guard result.matches(identity) else { throw CompanyConnectionError.identityMismatch }
        return result
    }

    func recordLifecycle(_ attempt: CompanyLifecycleAttempt, identity: CompanyIdentity) async throws -> CompanyLifecycleEvent {
        guard UUID(uuidString: attempt.caseID) != nil else { throw CompanyConnectionError.invalidResponse }
        guard identity.legalAccepted, ["owner", "admin"].contains(identity.role) else { throw CompanyConnectionError.http(403) }
        let encoder = JSONEncoder(); encoder.keyEncodingStrategy = .convertToSnakeCase; encoder.dateEncodingStrategy = .iso8601
        let event: CompanyLifecycleEvent = try await get("api/saas/company-portfolio/cases/\(attempt.caseID)/lifecycle", method: "POST", body: encoder.encode(attempt.payload))
        guard attempt.accepts(event, memberID: identity.memberId) else { throw CompanyConnectionError.identityMismatch }
        return event
    }

    func readiness(item: CompanyCase, event: CompanyLifecycleEvent, identity: CompanyIdentity, bind: CompanyReadinessBinding? = nil) async throws -> CompanyReadinessBinding {
        guard UUID(uuidString: item.caseId) != nil, UUID(uuidString: event.eventId) != nil, item.isCommercial, event.stage == .ready, !event.readinessStale else { throw CompanyConnectionError.invalidResponse }
        var body: Data?
        if let bind {
            guard identity.legalAccepted, ["owner", "admin"].contains(identity.role), bind.matches(identity, item: item, event: event), bind.canBind else { throw CompanyConnectionError.http(409) }
            body = try JSONSerialization.data(withJSONObject: ["ready_event_id": bind.readyEventId, "projection_sha256": bind.projectionSha256, "acknowledge_partial_coverage": true])
        }
        let result: CompanyReadinessBinding = try await get("api/saas/company-portfolio/cases/\(item.caseId)/readiness-evidence", method: body == nil ? "GET" : "POST", body: body)
        guard result.matches(identity, item: item, event: event) else { throw CompanyConnectionError.identityMismatch }
        if let bind, !result.bindingCurrent || result.projectionSha256 != bind.projectionSha256 { throw CompanyConnectionError.http(409) }
        return result
    }

    private func artifactPath(_ event: CompanyLifecycleEvent, item: CompanyCase) throws -> String {
        guard UUID(uuidString: item.caseId) != nil, UUID(uuidString: event.eventId) != nil, event.matches(caseID: item.caseId), !event.stage.isPreparation else { throw CompanyConnectionError.invalidResponse }
        return "api/saas/company-portfolio/cases/\(item.caseId)/lifecycle/\(event.eventId)/artifact"
    }

    func eventArtifact(item: CompanyCase, event: CompanyLifecycleEvent, identity: CompanyIdentity, upload: CompanyArtifactBytes? = nil) async throws -> CompanyEventArtifact {
        let path = try artifactPath(event, item: item)
        var query: [URLQueryItem] = []
        if let upload {
            guard identity.legalAccepted, ["owner", "admin"].contains(identity.role) else { throw CompanyConnectionError.http(403) }
            query = [URLQueryItem(name:"format_hint",value:upload.format), URLQueryItem(name:"confirm_user_supplied",value:"true")]
        }
        let result: CompanyEventArtifact = try await get(path, query: query, method: upload == nil ? "GET" : "POST", body: upload?.data, contentType: "application/octet-stream")
        guard result.matches(identity, event: event), upload.map(result.accepts) ?? true else { throw CompanyConnectionError.identityMismatch }
        return result
    }

    func downloadEventArtifact(item: CompanyCase, event: CompanyLifecycleEvent, identity: CompanyIdentity, artifact: CompanyEventArtifact) async throws -> CompanyArtifactBytes {
        guard artifact.matches(identity, event: event) else { throw CompanyConnectionError.identityMismatch }
        let path = try artifactPath(event, item: item) + "/download"
        return try await downloadVerifiedFile(path:path,sha:artifact.inspection.sha256,size:artifact.inspection.sizeBytes,format:artifact.formatHint)
    }

    private func downloadVerifiedFile(path: String, sha: String, size: Int, format: String) async throws -> CompanyArtifactBytes {
        guard CompanyArtifactBytes.validDigest(sha), (1...CompanyArtifactBytes.limit).contains(size), CompanyArtifactBytes.formats.contains(format) else { throw CompanyConnectionError.invalidArtifact }
        var request = URLRequest(url: baseURL.appending(path: path), cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/octet-stream", forHTTPHeaderField: "Accept")
        let (stream, response) = try await session.bytes(for: request)
        defer { stream.task.cancel() }
        guard let http = response as? HTTPURLResponse else { throw CompanyConnectionError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw CompanyConnectionError.http(http.statusCode) }
        guard http.value(forHTTPHeaderField: "X-Artifact-SHA256") == sha else { throw CompanyConnectionError.invalidArtifact }
        var data = Data(); data.reserveCapacity(size)
        for try await byte in stream {
            guard data.count < size else { throw CompanyConnectionError.invalidArtifact }
            data.append(byte)
        }
        let bytes = try CompanyArtifactBytes(data: data, format: format)
        guard bytes.sha256==sha, bytes.data.count==size else { throw CompanyConnectionError.invalidArtifact }
        return bytes
    }

    private func pricePath(caseID: String, identity: CompanyIdentity, write: Bool = false) throws -> String {
        guard UUID(uuidString: caseID) != nil, identity.legalAccepted, (write ? ["owner", "admin"] : ["owner", "admin", "analyst"]).contains(identity.role) else { throw CompanyConnectionError.http(403) }
        return "api/saas/company-portfolio/cases/\(caseID)/price-scenarios"
    }

    func pricePreview(caseID: String, identity: CompanyIdentity, input: CompanyPriceInput) async throws -> CompanyPricePreview {
        guard input.valid else { throw CompanyConnectionError.invalidPrice }
        let encoder = JSONEncoder(); encoder.keyEncodingStrategy = .convertToSnakeCase
        let reply: CompanyPricePreview = try await get(try pricePath(caseID: caseID, identity: identity) + "/preview", method: "POST", body: encoder.encode(input))
        guard reply.matches(identity, caseID: caseID, input: input) else { throw CompanyConnectionError.identityMismatch }
        return reply
    }

    func itemizedPreview(caseID: String, identity: CompanyIdentity, estimate: CompanyItemizedInput) async throws -> CompanyItemizedPreview {
        guard let sums=estimate.sums, estimate.terms.aggregate(sums.mapValues { NSDecimalNumber(decimal:$0).stringValue }).valid else { throw CompanyConnectionError.invalidPrice }
        let encoder=JSONEncoder(); encoder.keyEncodingStrategy = .convertToSnakeCase
        let reply: CompanyItemizedPreview = try await get(try pricePath(caseID:caseID,identity:identity)+"/itemized/preview",method:"POST",body:encoder.encode(estimate))
        guard reply.matches(identity,caseID:caseID,estimate:estimate) else { throw CompanyConnectionError.identityMismatch }
        return reply
    }

    func priceHistory(caseID: String, identity: CompanyIdentity) async throws -> CompanyPriceHistory {
        let reply: CompanyPriceHistory = try await get(try pricePath(caseID: caseID, identity: identity), query: [URLQueryItem(name:"limit", value:"30")])
        guard reply.matches(identity, caseID: caseID) else { throw CompanyConnectionError.identityMismatch }
        return reply
    }

    func savePrice(_ attempt: CompanyPriceAttempt, identity: CompanyIdentity) async throws -> CompanyPriceRecord {
        let encoder = JSONEncoder(); encoder.keyEncodingStrategy = .convertToSnakeCase
        let path = try pricePath(caseID:attempt.caseID,identity:identity,write:true)
        let reply: CompanyPriceRecord
        if let itemized=attempt.itemized {
            reply = try await get(path+"/itemized",method:"POST",body:encoder.encode(CompanyItemizedSavePayload(expectedRevision:attempt.payload.expectedRevision,idempotencyKey:attempt.payload.idempotencyKey,estimate:itemized.inputs)))
        } else { reply = try await get(path,method:"POST",body:encoder.encode(attempt.payload)) }
        guard attempt.accepts(reply,identity:identity) else { throw CompanyConnectionError.identityMismatch }
        return reply
    }

    private func costPath(caseID: String, identity: CompanyIdentity, target: CompanyCostTarget, write: Bool = false) throws -> String {
        guard target.matches(identity,caseID:caseID) else { throw CompanyConnectionError.identityMismatch }
        return try pricePath(caseID:caseID,identity:identity,write:write)+"/\(target.scenario.scenarioId)/lines/\(target.line.ordinal)/evidence"
    }

    func costBinding(caseID: String, identity: CompanyIdentity,target: CompanyCostTarget) async throws -> CompanyCostBinding {
        let result: CompanyCostBinding = try await get(try costPath(caseID:caseID,identity:identity,target:target))
        guard result.matches(identity,caseID:caseID,target:target) else { throw CompanyConnectionError.identityMismatch }; return result
    }

    func saveCostEvidence(caseID: String, identity: CompanyIdentity,target: CompanyCostTarget,binding: CompanyCostBinding,kind: CompanyCostDocumentKind,bytes: CompanyArtifactBytes) async throws -> CompanyCostEvidence {
        guard binding.matches(identity,caseID:caseID,target:target), binding.evidence==nil else { throw CompanyConnectionError.http(409) }
        let path=try costPath(caseID:caseID,identity:identity,target:target,write:true)
        let query=[URLQueryItem(name:"format_hint",value:bytes.format),URLQueryItem(name:"document_kind",value:kind.rawValue),URLQueryItem(name:"line_sha256",value:target.digest),URLQueryItem(name:"confirm_user_supplied",value:"true")]
        let result: CompanyCostEvidence = try await get(path,query:query,method:"POST",body:bytes.data,contentType:"application/octet-stream")
        guard result.matches(identity,caseID:caseID,target:target), result.scope==binding.scope, result.memberId==identity.memberId, result.documentKind==kind, result.accepts(bytes) else { throw CompanyConnectionError.identityMismatch }; return result
    }

    func downloadCostEvidence(caseID: String, identity: CompanyIdentity,target: CompanyCostTarget,evidence: CompanyCostEvidence) async throws -> CompanyArtifactBytes {
        guard evidence.matches(identity,caseID:caseID,target:target) else { throw CompanyConnectionError.identityMismatch }
        let path=try costPath(caseID:caseID,identity:identity,target:target)+"/download"
        return try await downloadVerifiedFile(path:path,sha:evidence.inspection.sha256,size:evidence.inspection.sizeBytes,format:evidence.formatHint)
    }

    private func actualPath(caseID:String,identity:CompanyIdentity,baseline:CompanyActualBaseline,write:Bool=false)throws->String {
        guard baseline.scenario.matches(identity,caseID:caseID),baseline.scenario.itemizedEstimate != nil else {throw CompanyConnectionError.identityMismatch}
        return try pricePath(caseID:caseID,identity:identity,write:write)+"/\(baseline.scenario.scenarioId)/actual-costs"
    }
    func actualHistory(caseID:String,identity:CompanyIdentity,baseline:CompanyActualBaseline) async throws -> [CompanyActualRecord] {
        let path=try actualPath(caseID:caseID,identity:identity,baseline:baseline);var rows:[CompanyActualRecord]=[],more=true
        while more {
            let page:CompanyActualPage=try await get(path,query:[.init(name:"offset",value:String(rows.count)),.init(name:"limit",value:"10")])
            guard page.matches(identity,caseID:caseID,baseline:baseline),rows.count+page.items.count<=30 else {throw CompanyConnectionError.identityMismatch}
            rows+=page.items;more=page.hasMore;if more && rows.count>=30 {throw CompanyConnectionError.identityMismatch}
        }
        guard Set(rows.map(\.id)).count==rows.count,rows.enumerated().allSatisfy({$0.element.revision==rows.count-$0.offset}) else {throw CompanyConnectionError.identityMismatch};return rows
    }
    func actualPreview(caseID:String,identity:CompanyIdentity,baseline:CompanyActualBaseline,input:CompanyActualInput) async throws -> CompanyActualPreview {
        guard input.valid(baseline) else {throw CompanyConnectionError.invalidPrice};let encoder=JSONEncoder();encoder.keyEncodingStrategy = .convertToSnakeCase
        let reply:CompanyActualPreview=try await get(try actualPath(caseID:caseID,identity:identity,baseline:baseline)+"/preview",method:"POST",body:encoder.encode(input))
        guard reply.matches(identity,caseID:caseID,baseline:baseline,input:input) else {throw CompanyConnectionError.identityMismatch};return reply
    }
    func saveActual(caseID:String,identity:CompanyIdentity,baseline:CompanyActualBaseline,attempt:CompanyActualAttempt) async throws -> CompanyActualRecord {
        guard attempt.scenarioID==baseline.scenario.scenarioId,attempt.result.matches(attempt.payload.snapshot,baseline:baseline) else {throw CompanyConnectionError.invalidPrice};let encoder=JSONEncoder();encoder.keyEncodingStrategy = .convertToSnakeCase
        let reply:CompanyActualRecord=try await get(try actualPath(caseID:caseID,identity:identity,baseline:baseline,write:true),method:"POST",body:encoder.encode(attempt.payload))
        guard attempt.accepts(reply,identity:identity,caseID:caseID,baseline:baseline) else {throw CompanyConnectionError.identityMismatch};return reply
    }

    private func actualEvidencePath(caseID:String,identity:CompanyIdentity,target:CompanyActualEvidenceTarget,write:Bool=false)throws->String {
        guard target.matches(identity,caseID:caseID) else {throw CompanyConnectionError.identityMismatch}
        return try actualPath(caseID:caseID,identity:identity,baseline:target.baseline,write:write)+"/\(target.snapshot.snapshotId)/rows/\(target.row.kind)/\(target.row.ordinal)/evidence"
    }
    func actualEvidenceBinding(caseID:String,identity:CompanyIdentity,target:CompanyActualEvidenceTarget) async throws -> CompanyActualEvidenceBinding {
        let result:CompanyActualEvidenceBinding=try await get(try actualEvidencePath(caseID:caseID,identity:identity,target:target))
        guard result.matches(identity,caseID:caseID,target:target) else {throw CompanyConnectionError.identityMismatch};return result
    }
    func saveActualEvidence(caseID:String,identity:CompanyIdentity,target:CompanyActualEvidenceTarget,binding:CompanyActualEvidenceBinding,kind:CompanyActualDocumentKind,bytes:CompanyArtifactBytes) async throws -> CompanyActualEvidence {
        guard binding.matches(identity,caseID:caseID,target:target),binding.evidence==nil else {throw CompanyConnectionError.http(409)}
        let path=try actualEvidencePath(caseID:caseID,identity:identity,target:target,write:true)
        let query=[URLQueryItem(name:"format_hint",value:bytes.format),URLQueryItem(name:"document_kind",value:kind.rawValue),URLQueryItem(name:"line_sha256",value:try target.digest()),URLQueryItem(name:"confirm_user_supplied",value:"true")]
        let result:CompanyActualEvidence=try await get(path,query:query,method:"POST",body:bytes.data,contentType:"application/octet-stream")
        guard result.matches(identity,caseID:caseID,target:target),result.scope==binding.scope,result.memberId==identity.memberId,result.documentKind==kind,result.accepts(bytes) else {throw CompanyConnectionError.identityMismatch};return result
    }
    func downloadActualEvidence(caseID:String,identity:CompanyIdentity,target:CompanyActualEvidenceTarget,evidence:CompanyActualEvidence) async throws -> CompanyArtifactBytes {
        guard evidence.matches(identity,caseID:caseID,target:target) else {throw CompanyConnectionError.identityMismatch}
        return try await downloadVerifiedFile(path:actualEvidencePath(caseID:caseID,identity:identity,target:target)+"/download",sha:evidence.inspection.sha256,size:evidence.inspection.sizeBytes,format:evidence.formatHint)
    }

    func actualSamplePreview(identity:CompanyIdentity,selections:[CompanyActualSampleSelection],comparable:Bool,distinct:Bool) async throws -> CompanyActualSamplePreview {
        guard identity.legalAccepted,["owner","admin","analyst"].contains(identity.role) else {throw CompanyConnectionError.http(403)}
        let input=try CompanyActualSampleInput.make(selections,comparable:comparable,distinct:distinct)
        let encoder=JSONEncoder();encoder.keyEncodingStrategy = .convertToSnakeCase
        let result:CompanyActualSamplePreview=try await get("/api/saas/company-portfolio/actual-samples/preview",method:"POST",body:encoder.encode(input))
        guard result.matches(identity,input:input,selections:selections) else {throw CompanyConnectionError.identityMismatch};return result
    }

    func normPage(identity:CompanyIdentity,key:String?=nil,offset:Int=0) async throws -> CompanyNormPage {
        guard identity.legalAccepted,["owner","admin","analyst"].contains(identity.role),offset>=0,offset<=(key==nil ? 500:100),key.map(CompanyNormDigest.isSHA) ?? true else {throw CompanyConnectionError.http(403)}
        let page:CompanyNormPage=try await get("/api/saas/company-portfolio/cost-norms"+(key.map{"/"+$0} ?? ""),query:[.init(name:"offset",value:String(offset)),.init(name:"limit",value:"10")])
        guard page.matches(identity,key:key) else {throw CompanyConnectionError.identityMismatch};return page
    }
    func normPreview(identity:CompanyIdentity,proposal:CompanyNormProposal,selections:[CompanyActualSampleSelection]) async throws -> CompanyNormPreview {
        guard identity.legalAccepted,["owner","admin","analyst"].contains(identity.role),proposal.valid else {throw CompanyConnectionError.http(403)}
        let e=JSONEncoder();e.keyEncodingStrategy = .convertToSnakeCase
        let r:CompanyNormPreview=try await get("/api/saas/company-portfolio/cost-norms/preview",method:"POST",body:e.encode(proposal))
        guard r.matches(identity,proposal:proposal,selections:selections) else{throw CompanyConnectionError.identityMismatch};return r
    }
    func approveNorm(identity:CompanyIdentity,draft:CompanyNormPreview,attempt:CompanyNormApproval,selections:[CompanyActualSampleSelection]) async throws -> CompanyNormRecord {
        guard identity.legalAccepted,["owner","admin"].contains(identity.role),attempt.confirmInternalApproval,attempt.proposal==draft.proposal,attempt.previewSha256==draft.previewSha256,attempt.expectedRevision==draft.expectedRevision,draft.matches(identity,proposal:attempt.proposal,selections:selections) else {throw CompanyConnectionError.http(403)}
        let e=JSONEncoder();e.keyEncodingStrategy = .convertToSnakeCase
        let r:CompanyNormRecord=try await get("/api/saas/company-portfolio/cost-norms",method:"POST",body:e.encode(attempt))
        guard r.matches(identity),r.memberId==identity.memberId,r.normKey==draft.normKey,r.inputs.approval==attempt,r.action=="APPROVED" else{throw CompanyConnectionError.identityMismatch};return r
    }
    func withdrawNorm(identity:CompanyIdentity,record:CompanyNormRecord,attempt:CompanyNormWithdrawal) async throws -> CompanyNormRecord {
        guard identity.legalAccepted,["owner","admin"].contains(identity.role),record.matches(identity),record.action=="APPROVED",attempt.confirmWithdrawal,attempt.expectedRevision==record.revision,(10...2000).contains(attempt.rationale.unicodeScalars.count) else {throw CompanyConnectionError.http(403)}
        let e=JSONEncoder();e.keyEncodingStrategy = .convertToSnakeCase
        let r:CompanyNormRecord=try await get("/api/saas/company-portfolio/cost-norms/"+record.normKey+"/withdraw",method:"POST",body:e.encode(attempt))
        guard r.matches(identity),r.memberId==identity.memberId,r.normKey==record.normKey,r.inputs.withdrawal==attempt,r.action=="WITHDRAWN",r.result.withdrawnNormId==record.normId,r.result.withdrawnRecordSha256==record.recordSha256 else{throw CompanyConnectionError.identityMismatch};return r
    }

    func historicalCatalog(identity:CompanyIdentity,item:CompanyCase) async throws -> CompanyHistoricalCatalog {
        _=try CompanyHistoricalCatalog.context(identity:identity,item:item)
        let raw:CompanyHistoricalJSON=try await get("/api/saas/company-portfolio/cases/"+item.caseId+"/historical-comparables")
        return try .verified(raw,identity:identity,item:item)
    }
    func historicalPreview(identity:CompanyIdentity,item:CompanyCase,catalog:CompanyHistoricalCatalog,selection:CompanyHistoricalSelection) async throws -> CompanyHistoricalPreview {
        guard catalog.matches(identity:identity,item:item),selection.valid(in:catalog) else{throw CompanyConnectionError.invalidPrice}
        let e=JSONEncoder();e.keyEncodingStrategy = .convertToSnakeCase
        let raw:CompanyHistoricalJSON=try await get("/api/saas/company-portfolio/cases/"+item.caseId+"/historical-comparables/preview",method:"POST",body:e.encode(selection))
        return try .verified(raw,identity:identity,item:item,catalog:catalog,selection:selection)
    }

    private func get<T: Decodable>(_ path: String, query: [URLQueryItem] = [], method: String = "GET", body: Data? = nil, contentType: String = "application/json") async throws -> T {
        guard var parts = URLComponents(url: baseURL.appending(path: path), resolvingAgainstBaseURL: false) else { throw CompanyConnectionError.invalidOrigin }
        if !query.isEmpty { parts.queryItems = query }
        guard let url = parts.url else { throw CompanyConnectionError.invalidOrigin }
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
        request.httpMethod = method
        request.httpBody = body
        if body != nil { request.setValue(contentType, forHTTPHeaderField: "Content-Type") }
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw CompanyConnectionError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw CompanyConnectionError.http(http.statusCode) }
        return try TenderAgentJSON.makeDecoder().decode(T.self, from: data)
    }
}
