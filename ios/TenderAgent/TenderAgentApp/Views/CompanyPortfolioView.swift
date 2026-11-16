import SwiftUI

private struct CompanyCaseSelection: Identifiable {
    let accountID: String
    let item: CompanyCase
    var id: String { accountID + "|" + item.caseId }
}

struct CompanyPortfolioView: View {
    @StateObject private var store = CompanyStore()
    @State private var origin = BackendCredentialStore.defaultBaseURLString
    @State private var token = ""
    @State private var selectedCase: CompanyCaseSelection?
    @State private var confirmedOrigin = false
    @State private var removal: CompanyConnection?

    var body: some View {
        List {
            Section("Подключения компаний") {
                ForEach(store.connections) { account in
                    Button {
                        selectedCase = nil
                        Task { await store.select(account.id) }
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(account.identity.companyName).foregroundStyle(.primary)
                                Text("\(account.identity.role) · \(account.baseURL.host ?? "")")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            if store.selectedID == account.id { Image(systemName: "checkmark.circle.fill") }
                        }
                    }
                    .disabled(store.isBusy)
                    .swipeActions(allowsFullSwipe: false) {
                        Button("Удалить", role: .destructive) { removal = account }.disabled(store.isBusy)
                    }
                }
                DisclosureGroup("Добавить подключение") {
                    TextField("HTTPS-адрес", text: $origin)
                        .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    SecureField("Токен компании saas_…", text: $token)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                    Toggle("Доверяю этому серверу", isOn: $confirmedOrigin)
                    Text("Используйте токен из своего веб-кабинета. Токен владельца DTR не подходит.")
                        .font(.caption).foregroundStyle(.secondary)
                    Button("Подключить компанию") {
                        let supplied = token.trimmingCharacters(in: .whitespacesAndNewlines)
                        let address = origin
                        token = ""
                        confirmedOrigin = false
                        selectedCase = nil
                        Task { _ = await store.connect(origin: address, token: supplied) }
                    }.disabled(store.isBusy || !store.storageReady || !confirmedOrigin || token.isEmpty)
                }.onChange(of: origin) { _, _ in confirmedOrigin = false }
            }
            if let error = store.error {
                Section { Label(error, systemImage: "exclamationmark.triangle").foregroundStyle(.orange) }
            }
            if let notice = store.decisionNotice { Section { Label(notice, systemImage: "checkmark.circle") } }
            if store.isBusy { Section { ProgressView("Проверяем доступ…") } }
            if let identity = store.identity {
                Section("Текущая компания") {
                    LabeledContent("Компания", value: identity.companyName)
                    LabeledContent("Роль", value: identity.role)
                    if !identity.legalAccepted {
                        Text("Подтвердите условия пилота в веб-кабинете и обновите доступ.").foregroundStyle(.orange)
                        Button("Обновить доступ") { Task { await store.refresh() } }.disabled(store.isBusy)
                    }
                }
            }
            if store.loaded {
                Section("Очередь руководителя") {
                    Picker("Показывать", selection: Binding(get: { store.inboxFilter }, set: { filter in
                        selectedCase = nil
                        Task { await store.setInboxFilter(filter) }
                    })) {
                        ForEach(CompanyInboxFilter.allCases) { filter in Text(filter.title).tag(filter) }
                    }.disabled(store.isBusy)
                    if let summary = store.inboxSummary {
                        LabeledContent("Требуют внимания", value: String(summary.attention))
                        LabeledContent("Пора вернуться", value: String(summary.deferredDue))
                        LabeledContent("GO / NO GO", value: "\(summary.go) / \(summary.noGo)")
                        LabeledContent("Всего сохранено", value: String(summary.all))
                    }
                    if let asOf = store.inboxAsOf {
                        Text("На \(asOf.formatted(date: .abbreviated, time: .shortened)). Обновите после изменений.").font(.caption).foregroundStyle(.secondary)
                    }
                    Text("Внутренние решения. Срок возврата не является сроком подачи заявки.").font(.caption).foregroundStyle(.secondary)
                    if store.items.isEmpty { Text("В этой очереди пока нет карточек.") }
                    ForEach(store.items) { item in
                        Button {
                            if let accountID = store.selectedID { selectedCase = CompanyCaseSelection(accountID: accountID, item: item) }
                        } label: {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(item.displayReference.isEmpty ? "Номер не указан" : item.displayReference).font(.headline)
                                Text(item.decision?.action ?? "Решение не принято")
                                if item.inboxState == "deferred_due" { Label("Пора вернуться к решению", systemImage: "clock").foregroundStyle(.orange).font(.caption) }
                                Text(item.isCommercial ? "Коммерческая ссылка · требуется проверка" : "Ссылка на ЕИС · требуется проверка").font(.caption).foregroundStyle(.secondary)
                            }.foregroundStyle(.primary)
                        }.disabled(store.isBusy)
                    }
                    if store.hasMore { Button("Показать ещё") { Task { await store.nextPage() } }.disabled(store.isBusy) }
                }
            }
        }
        .navigationTitle("Компании")
        .refreshable { await store.refresh() }
        .sheet(item: $selectedCase) { choice in CompanyCaseDetail(item: choice.item, accountID: choice.accountID, store: store) }
        .alert("Удалить подключение с устройства?", isPresented: Binding(get: { removal != nil }, set: { if !$0 { removal = nil } })) {
            Button("Удалить", role: .destructive) {
                if let account = removal { store.forget(account.id) }
                removal = nil
            }
            Button("Отмена", role: .cancel) { removal = nil }
        } message: { Text("Токен удаляется только из приложения. Для отзыва доступа используйте веб-кабинет.") }
    }
}

private struct CompanyCaseDetail: View {
    let item: CompanyCase
    let accountID: String
    @ObservedObject var store: CompanyStore
    @Environment(\.dismiss) private var dismiss
    @State private var evidence: CompanyEvidencePage?
    @State private var error: String?
    @State private var action: MobileDecisionAction = .go
    @State private var rationale = ""
    @State private var deferredUntil = Date().addingTimeInterval(86400)
    @State private var decisionError: String?
    @State private var prepared: CompanyDecisionDraft?
    @State private var showConfirmation = false

    private var canDecide: Bool {
        store.canDecide(accountID: accountID, caseID: item.caseId, revision: item.revision)
    }

    var body: some View {
        NavigationStack {
            List {
                Section("Закупка") {
                    Text(item.displayReference.isEmpty ? "Номер не указан" : item.displayReference)
                    if item.isCommercial, let url = item.sourceUrl { Text(url).font(.caption).textSelection(.enabled) }
                    Text("Идентификатор закупки не подтверждает актуальный правовой статус.").font(.caption).foregroundStyle(.secondary)
                }
                Section("Решение компании") {
                    if let decision = item.decision {
                        LabeledContent("Действие", value: decision.action)
                        Text(decision.rationale)
                        LabeledContent("Версия", value: String(decision.revision))
                        if let due = decision.deferredUntil { Text(due, style: .date) }
                    } else { Text("Решение не принято") }
                    Text("Внутреннее решение. Отправка заявок недоступна.").font(.caption).foregroundStyle(.secondary)
                }
                if canDecide {
                    Section("Изменить решение") {
                        Picker("Действие", selection: $action) {
                            ForEach(MobileDecisionAction.allCases) { candidate in Text(candidate.displayTitle).tag(candidate) }
                        }
                        if action == .deferDecision {
                            DatePicker("Отложить до", selection: $deferredUntil, in: Date()...)
                        }
                        TextField("Обоснование", text: $rationale, axis: .vertical).lineLimit(3...6)
                        Button("Проверить и подтвердить") {
                            decisionError = nil
                            do {
                                prepared = try CompanyDecisionDraft(action: action.rawValue, rationale: rationale,
                                    deferredUntil: action == .deferDecision ? deferredUntil : nil, expectedRevision: item.revision)
                                showConfirmation = true
                            } catch { decisionError = CompanyStore.safeError(error) }
                        }
                        .disabled(store.isBusy || rationale.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                    .disabled(store.isBusy)
                } else if let identity = store.identity, ["owner", "admin"].contains(identity.role) {
                    Section { Text("Карточка изменилась или недоступна. Откройте её заново.").foregroundStyle(.orange) }
                }
                if let decisionError { Section { Text(decisionError).foregroundStyle(.orange) } }
                if !item.isCommercial, let identity = store.identity, ["owner", "admin", "analyst"].contains(identity.role) {
                    Section("Привязанные источники") {
                        if let evidence {
                            if evidence.items.isEmpty { Text("Документы ещё не привязаны") }
                            ForEach(evidence.items) { source in
                                VStack(alignment: .leading) {
                                    Text(source.runId).font(.caption.monospaced())
                                    Text("Профиль v\(source.profileVersion) · \(source.profileState)")
                                }
                            }
                            if evidence.hasMore { Text("Показаны первые 50 привязок").font(.caption) }
                            Text("Привязка не означает повторной проверки оригиналов или актуальной квалификации.").font(.caption).foregroundStyle(.secondary)
                        } else if let error { Text(error).foregroundStyle(.orange) }
                        else { ProgressView() }
                    }
                }
            }
            .navigationTitle("Карточка компании")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Готово") { dismiss() } } }
            .alert("Подтвердить решение?", isPresented: $showConfirmation) {
                Button("Сохранить") {
                    guard let draft = prepared else { return }
                    prepared = nil
                    Task {
                        do {
                            try await store.submitDecision(accountID: accountID, caseID: item.caseId, draft: draft)
                            dismiss()
                        } catch { decisionError = CompanyStore.safeError(error) }
                    }
                }
                Button("Отмена", role: .cancel) { prepared = nil }
            } message: {
                Text("\(store.identity?.companyName ?? "Компания") · \(item.displayReference) · \(prepared?.action ?? "—") · версия \(item.revision). Это не подача заявки.")
            }
            .onChange(of: store.selectedID) { _, value in if value != accountID { dismiss() } }
            .onChange(of: store.identity?.memberId) { _, value in if value == nil { dismiss() } }
            .task {
                guard !item.isCommercial, let identity = store.identity, ["owner", "admin", "analyst"].contains(identity.role) else { return }
                do { evidence = try await store.evidence(for: item.caseId) }
                catch { self.error = CompanyStore.safeError(error) }
            }
        }
    }
}
