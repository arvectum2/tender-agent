import SwiftUI

struct PortfolioView: View {
    @EnvironmentObject private var store: AppStore
    @State private var selectedFilter: PortfolioFilter = .all

    private let columns = [
        GridItem(.flexible(), spacing: 12),
        GridItem(.flexible(), spacing: 12)
    ]

    private var filteredItems: [Procurement] {
        store.portfolioItems(for: selectedFilter)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if store.isMockData || !store.isLive {
                    Label(
                        store.isMockData
                            ? "Демо-портфель — backend не подключён"
                            : "Показаны последние данные: backend недоступен",
                        systemImage: store.isMockData ? "testtube.2" : "wifi.exclamationmark"
                    )
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }

                LazyVGrid(columns: columns, spacing: 12) {
                    MetricCard(value: "\(store.totalPortfolioCount)", title: "Рассмотрено")
                    MetricCard(value: "\(store.goCount)", title: "GO")
                    MetricCard(value: "\(store.submittedCount)", title: "Подались")
                    MetricCard(value: "\(store.wonCount)", title: "Выиграли")
                }

                outcomeMetrics

                VStack(alignment: .leading, spacing: 10) {
                    Text("Срез портфеля")
                        .font(.headline)

                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(PortfolioFilter.allCases) { filter in
                                filterButton(filter)
                            }
                        }
                    }
                }

                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text(selectedFilter.title)
                            .font(.headline)
                        Spacer()
                        Text("\(filteredItems.count)")
                            .font(.caption.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }

                    if filteredItems.isEmpty {
                        ContentUnavailableView(
                            "В этом срезе нет закупок",
                            systemImage: "line.3.horizontal.decrease.circle",
                            description: Text("Фильтр использует только канонические факты портфеля.")
                        )
                        .frame(maxWidth: .infinity)
                    } else {
                        ForEach(filteredItems) { procurement in
                            NavigationLink(value: procurement.id) {
                                PortfolioRow(procurement: procurement)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            .padding()
        }
        .navigationTitle("Портфель")
        .refreshable {
            await store.refresh()
        }
    }

    private var outcomeMetrics: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Воронка и результаты")
                .font(.headline)

            HStack(spacing: 10) {
                compactMetric(percent(store.submissionRate), "GO → подача")
                compactMetric(percent(store.winRate), "Win rate")
            }

            HStack(spacing: 10) {
                compactMetric("\(store.notWonCount)", "Не выиграли")
                compactMetric("\(store.cancelledCount)", "Отменены")
            }

            Text("Submission rate = подались / GO. Win rate = победы / (победы + проигрыши + отклонённые заявки).")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }

    private func compactMetric(_ value: String, _ title: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(value)
                .font(.headline.monospacedDigit())
            Text(title)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    private func filterButton(_ filter: PortfolioFilter) -> some View {
        let selected = selectedFilter == filter
        return Button {
            selectedFilter = filter
        } label: {
            HStack(spacing: 5) {
                Text(filter.title)
                Text("\(store.portfolioCount(for: filter))")
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(selected ? .primary : .secondary)
            }
            .font(.caption.bold())
            .padding(.horizontal, 11)
            .padding(.vertical, 8)
            .background(
                selected ? Color.accentColor.opacity(0.18) : Color.secondary.opacity(0.08),
                in: Capsule()
            )
        }
        .buttonStyle(.plain)
    }

    private func percent(_ value: Double) -> String {
        value.formatted(.percent.precision(.fractionLength(0)))
    }
}

private struct PortfolioRow: View {
    let procurement: Procurement

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(procurement.registryNumber)
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                Spacer()
                Text(procurement.portfolioStateLabel)
                    .font(.caption.bold())
                    .foregroundStyle(statusTint)
            }

            Text(procurement.title)
                .font(.subheadline.weight(.semibold))
                .lineLimit(2)

            Text(procurement.customer)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)

            HStack {
                Label(procurement.formattedNMCK, systemImage: "rublesign.circle")
                Spacer()
                if procurement.needsAttention {
                    Label("Нужно решение", systemImage: "person.crop.circle.badge.exclamationmark")
                } else if procurement.submitted && procurement.outcomeCode == nil {
                    Label("Ждём итог", systemImage: "hourglass")
                } else {
                    Label(procurement.decision.rawValue, systemImage: "person.crop.circle")
                }
            }
            .font(.caption2)
            .foregroundStyle(.secondary)
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    private var statusTint: Color {
        switch procurement.outcomeCode {
        case "WON":
            return .green
        case "LOST", "REJECTED":
            return .red
        case "CANCELLED":
            return .orange
        default:
            switch procurement.portfolioDecision {
            case .go: return .green
            case .noGo: return .red
            case .needsReview: return .orange
            case .undecided: return .secondary
            }
        }
    }
}
