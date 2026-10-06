import SwiftUI

struct ProcurementDetailView: View {
    @EnvironmentObject private var store: AppStore
    let procurementID: String

    private var procurement: Procurement? {
        store.procurement(id: procurementID)
    }

    var body: some View {
        Group {
            if let procurement {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        header(procurement)
                        recommendationCard(procurement)
                        summarySection(procurement)
                        bulletSection("Аргументы GO", items: procurement.goReasons, symbol: "checkmark.circle")
                        bulletSection("Аргументы NO GO", items: procurement.noGoReasons, symbol: "xmark.circle")
                        bulletSection("Блокеры", items: procurement.blockers, symbol: "exclamationmark.octagon")
                        bulletSection("Неопределённости", items: procurement.unknowns, symbol: "questionmark.circle")
                        bulletSection("Риски исполнения", items: procurement.risks, symbol: "exclamationmark.triangle")
                        humanDecisionSection(procurement)

                        if let sourceURL = procurement.sourceURL {
                            Link(destination: sourceURL) {
                                Label("Открыть в ЕИС", systemImage: "arrow.up.right.square")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                    .padding()
                }
                .navigationTitle(procurement.registryNumber)
                .navigationBarTitleDisplayMode(.inline)
            } else {
                ContentUnavailableView("Закупка не найдена", systemImage: "doc.text.magnifyingglass")
            }
        }
    }

    private func header(_ procurement: Procurement) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                RecommendationBadge(recommendation: procurement.recommendation)
                Spacer()
                Text(procurement.lifecycle.rawValue)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text(procurement.title)
                .font(.title2.bold())

            Text(procurement.customer)
                .foregroundStyle(.secondary)

            HStack {
                Label(procurement.formattedNMCK, systemImage: "rublesign.circle")
                Spacer()
                Label(
                    procurement.deadline.map { _ in "\(procurement.deadlineText) до срока" }
                        ?? procurement.deadlineText,
                    systemImage: "clock"
                )
            }
            .font(.subheadline)
        }
    }

    private func recommendationCard(_ procurement: Procurement) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Рекомендация агента")
                .font(.caption)
                .foregroundStyle(.secondary)
            HStack {
                Text(procurement.recommendation.rawValue)
                    .font(.title2.bold())
                Spacer()
                if let confidence = procurement.confidenceLabel, !confidence.isEmpty {
                    Text("Уверенность: \(confidence)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private func summarySection(_ procurement: Procurement) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Саммари")
                .font(.headline)
            Text(procurement.summary)
                .foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private func bulletSection(_ title: String, items: [String], symbol: String) -> some View {
        if !items.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                Text(title)
                    .font(.headline)
                ForEach(items, id: \.self) { item in
                    Label(item, systemImage: symbol)
                        .font(.subheadline)
                }
            }
        }
    }

    private func humanDecisionSection(_ procurement: Procurement) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Решение менеджера")
                .font(.headline)
            Text(procurement.decision.rawValue)
                .font(.subheadline.bold())
            if let comment = procurement.decisionComment, !comment.isEmpty {
                Text(comment)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            if let deferredUntil = procurement.deferredUntil {
                Text(
                    "Вернуться: \(deferredUntil.formatted(date: .abbreviated, time: .shortened))"
                )
                .font(.caption)
                .foregroundStyle(.secondary)
            }
            Text("MOB-1 — только чтение. GO / NO GO / DEFER появятся отдельным управляемым этапом.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }
}
