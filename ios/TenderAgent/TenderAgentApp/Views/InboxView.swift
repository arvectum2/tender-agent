import SwiftUI

struct InboxView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        List {
            if store.isMockData || !store.isLive {
                Section {
                    Label(
                        store.isMockData
                            ? "Демо-данные — backend не подключён"
                            : "Нет соединения с backend",
                        systemImage: store.isMockData
                            ? "testtube.2"
                            : "wifi.exclamationmark"
                    )
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
            }

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
                        description: Text(
                            store.isLive
                                ? "Новые manager-ready отчёты появятся здесь после Daily Tender Run."
                                : "Подключите Mac mini, чтобы увидеть live manager inbox."
                        )
                    )
                } else {
                    ForEach(store.decisionNeeded) { procurement in
                        NavigationLink(value: procurement.id) {
                            ProcurementRow(procurement: procurement)
                        }
                    }
                }
            }
        }
        .navigationTitle("Tender Agent")
        .refreshable {
            await store.refresh()
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
                    Text(store.isLive ? "Live manager inbox" : "Демо-режим")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: store.isLive ? "checkmark.seal.fill" : "testtube.2")
                    .foregroundStyle(store.isLive ? .green : .orange)
            }

            HStack(spacing: 12) {
                digestMetric("\(store.totalPortfolioCount)", "в портфеле")
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
