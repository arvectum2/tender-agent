import SwiftUI

struct PortfolioView: View {
    @EnvironmentObject private var store: AppStore

    private let columns = [
        GridItem(.flexible(), spacing: 12),
        GridItem(.flexible(), spacing: 12)
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                LazyVGrid(columns: columns, spacing: 12) {
                    MetricCard(value: "\(store.procurements.count)", title: "Отобрано")
                    MetricCard(value: "\(store.goCount)", title: "GO")
                    MetricCard(value: "\(store.noGoCount)", title: "NO GO")
                    MetricCard(value: "\(store.submittedCount)", title: "Подались")
                }

                VStack(alignment: .leading, spacing: 12) {
                    Text("Последние закупки")
                        .font(.headline)

                    ForEach(store.procurements) { procurement in
                        NavigationLink(value: procurement.id) {
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(procurement.registryNumber)
                                        .font(.caption.monospacedDigit())
                                        .foregroundStyle(.secondary)
                                    Text(procurement.title)
                                        .font(.subheadline)
                                        .lineLimit(2)
                                }

                                Spacer()

                                Text(procurement.decision.rawValue)
                                    .font(.caption.bold())
                                    .foregroundStyle(decisionColor(procurement.decision))
                            }
                            .padding()
                            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 14))
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .padding()
        }
        .navigationTitle("Портфель")
        .navigationDestination(for: String.self) { id in
            ProcurementDetailView(procurementID: id)
        }
        .refreshable {
            await store.refresh()
        }
    }

    private func decisionColor(_ decision: HumanDecision) -> Color {
        switch decision {
        case .go: .green
        case .noGo: .red
        case .deferred: .orange
        case .pending: .secondary
        }
    }
}
