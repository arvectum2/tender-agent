import SwiftUI

struct ProcurementDetailView: View {
    @EnvironmentObject private var store: AppStore
    let procurementID: String

    @State private var showDeferSheet = false
    @State private var deferUntil = Calendar.current.date(byAdding: .day, value: 1, to: .now) ?? .now

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

                        if let sourceURL = procurement.sourceURL {
                            Link(destination: sourceURL) {
                                Label("Открыть в ЕИС", systemImage: "arrow.up.right.square")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                    .padding()
                    .padding(.bottom, 92)
                }
                .safeAreaInset(edge: .bottom) {
                    decisionBar(procurement)
                }
                .sheet(isPresented: $showDeferSheet) {
                    deferSheet(procurement)
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
                Label(procurement.deadline.map { _ in "\(procurement.deadlineText) до срока" } ?? procurement.deadlineText, systemImage: "clock")
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
                if let confidence = procurement.confidence {
                    Text("\(Int(confidence * 100))% уверенность")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            if let confidence = procurement.confidence {
                ProgressView(value: confidence)
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

    private func decisionBar(_ procurement: Procurement) -> some View {
        HStack(spacing: 10) {
            Button("NO GO") {
                Task {
                    await store.submitDecision(.noGo, for: procurement.id)
                }
            }
            .buttonStyle(.bordered)
            .tint(.red)

            Button("Отложить") {
                showDeferSheet = true
            }
            .buttonStyle(.bordered)

            Button("GO") {
                Task {
                    await store.submitDecision(.go, for: procurement.id)
                }
            }
            .buttonStyle(.borderedProminent)
            .tint(.green)
        }
        .padding()
        .background(.bar)
    }

    private func deferSheet(_ procurement: Procurement) -> some View {
        NavigationStack {
            Form {
                DatePicker(
                    "Вернуть к решению",
                    selection: $deferUntil,
                    in: Date.now...,
                    displayedComponents: [.date, .hourAndMinute]
                )
            }
            .navigationTitle("Отложить")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Отмена") {
                        showDeferSheet = false
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Готово") {
                        Task {
                            await store.submitDecision(
                                .deferred,
                                for: procurement.id,
                                deferredUntil: deferUntil
                            )
                        }
                        showDeferSheet = false
                    }
                }
            }
        }
        .presentationDetents([.medium])
    }
}
