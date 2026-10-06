import SwiftUI

struct ProcurementDetailView: View {
    @EnvironmentObject private var store: AppStore
    let procurementID: String

    @State private var pendingAction: MobileDecisionAction?

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
                .sheet(item: $pendingAction) { action in
                    DecisionComposerView(
                        procurement: procurement,
                        action: action
                    )
                    .environmentObject(store)
                }
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
        VStack(alignment: .leading, spacing: 12) {
            Text("Решение менеджера")
                .font(.headline)

            HStack {
                Text(procurement.decision.rawValue)
                    .font(.subheadline.bold())
                Spacer()
                if store.isSubmittingDecision(for: procurement.id) {
                    ProgressView()
                        .controlSize(.small)
                }
            }

            if let comment = procurement.decisionComment, !comment.isEmpty {
                Text(comment)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            if let deferredUntil = procurement.deferredUntil {
                Text("Вернуться: \(deferredUntil.formatted(date: .abbreviated, time: .shortened))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if store.lastDecisionDealID == procurement.id {
                if let message = store.decisionMessage {
                    Label(message, systemImage: "checkmark.circle.fill")
                        .font(.caption)
                        .foregroundStyle(.green)
                }
                if let error = store.decisionError {
                    Label(error, systemImage: "exclamationmark.triangle.fill")
                        .font(.caption)
                        .foregroundStyle(.red)
                }
            }

            VStack(spacing: 10) {
                HStack(spacing: 10) {
                    decisionButton("GO", action: .go, tint: .green)
                    decisionButton("NO GO", action: .noGo, tint: .red)
                }
                decisionButton("Отложить", action: .deferDecision, tint: .orange)
            }

            Text(
                store.canSubmitDecisions
                    ? "Действие записывается только после отдельного подтверждения и не запускает подачу заявки, ЭЦП или оплату."
                    : "Запись решений доступна только при подключённом live backend. Демо-данные не изменяются."
            )
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private func decisionButton(
        _ title: String,
        action: MobileDecisionAction,
        tint: Color
    ) -> some View {
        Button(title) {
            pendingAction = action
        }
        .buttonStyle(.borderedProminent)
        .tint(tint)
        .frame(maxWidth: .infinity)
        .disabled(!store.canSubmitDecisions || store.isSubmittingDecision(for: procurementID))
    }
}

private struct DecisionComposerView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var store: AppStore

    let procurement: Procurement
    let action: MobileDecisionAction

    @State private var rationale = ""
    @State private var deferredUntil = Date.now.addingTimeInterval(86_400)

    var body: some View {
        NavigationStack {
            Form {
                Section("Подтверждение") {
                    LabeledContent("Закупка", value: procurement.registryNumber)
                    LabeledContent("Решение", value: action.displayTitle)
                    Text("Решение будет записано как действие человека в канонический журнал Tender Agent.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if action == .deferDecision {
                    Section("Вернуться к закупке") {
                        DatePicker(
                            "Дата и время",
                            selection: $deferredUntil,
                            in: Date.now...,
                            displayedComponents: [.date, .hourAndMinute]
                        )
                    }
                }

                Section("Комментарий — необязательно") {
                    TextEditor(text: $rationale)
                        .frame(minHeight: 100)
                }

                if store.lastDecisionDealID == procurement.id,
                   let error = store.decisionError {
                    Section {
                        Label(error, systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle(action.displayTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Отмена") { dismiss() }
                        .disabled(store.isSubmittingDecision(for: procurement.id))
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Сохранить") {
                        Task {
                            let saved = await store.submitDecision(
                                dealID: procurement.id,
                                action: action,
                                rationale: rationale,
                                deferredUntil: action == .deferDecision ? deferredUntil : nil
                            )
                            if saved {
                                dismiss()
                            }
                        }
                    }
                    .disabled(store.isSubmittingDecision(for: procurement.id))
                }
            }
            .overlay {
                if store.isSubmittingDecision(for: procurement.id) {
                    ProgressView("Сохраняю решение…")
                        .padding()
                        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}
