import SwiftUI

struct InboxView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        List {
            Section {
                DailyDigestView()
                    .listRowInsets(EdgeInsets())
                    .listRowBackground(Color.clear)
            }

            Section("Требуют решения") {
                if store.decisionNeeded.isEmpty {
                    ContentUnavailableView(
                        "Решений не требуется",
                        systemImage: "checkmark.circle",
                        description: Text("Новые отчёты появятся здесь после Daily Tender Run.")
                    )
                } else {
                    ForEach(store.decisionNeeded) { procurement in
                        NavigationLink(value: procurement.id) {
                            ProcurementRow(procurement: procurement)
                        }
                    }
                }
            }

            Section("Уже обработаны") {
                ForEach(store.procurements.filter { $0.decision == .go || $0.decision == .noGo }) { procurement in
                    NavigationLink(value: procurement.id) {
                        ProcurementRow(procurement: procurement)
                    }
                }
            }
        }
        .navigationTitle("Tender Agent")
        .navigationDestination(for: String.self) { id in
            ProcurementDetailView(procurementID: id)
        }
    }
}

private struct DailyDigestView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Daily Tender Run")
                        .font(.headline)
                    Text("Последний запуск • сегодня")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "checkmark.seal.fill")
                    .foregroundStyle(.green)
            }

            HStack(spacing: 12) {
                digestMetric("\(store.procurements.count)", "разобрано")
                digestMetric("\(store.decisionNeeded.count)", "ждут решения")
                digestMetric("\(store.submittedCount)", "подались")
            }
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18))
        .padding(.vertical, 4)
    }

    private func digestMetric(_ value: String, _ label: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value)
                .font(.title3.bold())
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct ProcurementRow: View {
    let procurement: Procurement

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(procurement.registryNumber)
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                Spacer()
                RecommendationBadge(recommendation: procurement.recommendation)
            }

            Text(procurement.title)
                .font(.headline)
                .lineLimit(2)

            Text(procurement.customer)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(1)

            HStack {
                Label(procurement.formattedNMCK, systemImage: "rublesign.circle")
                Spacer()
                Label(procurement.deadlineText, systemImage: "clock")
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }
}

struct RecommendationBadge: View {
    let recommendation: AgentRecommendation

    private var tint: Color {
        switch recommendation {
        case .go: .green
        case .noGo: .red
        case .review: .orange
        case .undecided: .secondary
        }
    }

    var body: some View {
        Text(recommendation.rawValue)
            .font(.caption2.bold())
            .foregroundStyle(tint)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(tint.opacity(0.12), in: Capsule())
    }
}
