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
                Section("Коммерческая статистика") {
                    Button("Обновить статистику") { Task { await store.refreshLifecycleMetrics() } }.disabled(store.isBusy)
                    if let metrics = store.lifecycleMetrics {
                        LabeledContent("Сохранено", value: String(metrics.savedCases))
                        LabeledContent("Когда-либо GO", value: String(metrics.everGoCases))
                        LabeledContent("Зарегистрировано заявок", value: String(metrics.recordedSubmissions))
                        LabeledContent("GO → подача", value: metrics.goToSubmission.display)
                        LabeledContent("Win rate", value: metrics.winRate.display)
                        Text("Победы / (победы + проигрыши + отклонения). За всё время, по сведениям сотрудников, на \(metrics.asOf.formatted()). Не проверенная выручка и не статистика всего рынка.").font(.caption).foregroundStyle(.secondary)
                    }
                    if let notice = store.lifecycleNotice { Text(notice).font(.caption).foregroundStyle(.orange) }
                }
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
                CompanyLifecycleSection(item: item, accountID: accountID, store: store)
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

private struct CompanyLifecycleSection: View {
    let item: CompanyCase
    let accountID: String
    @ObservedObject var store: CompanyStore
    @State private var state: CompanyLifecycleState?
    @State private var history: CompanyLifecycleHistory?
    @State private var stage: CompanyLifecycleStage = .preparing
    @State private var rationale = ""
    @State private var sourceRef = ""
    @State private var occurredAt = Date()
    @State private var notice: String?
    @State private var draft: CompanyLifecycleDraft?
    @State private var confirm = false

    private var canWrite: Bool { store.canDecide(accountID: accountID, caseID: item.caseId, revision: item.revision) }
    private func reload() async {
        state = nil; history = nil; draft = nil
        notice = nil
        do {
            let result = try await store.loadLifecycle(accountID: accountID, item: item)
            state = result
            if let first = result.options.first { stage = first }
        } catch { notice = CompanyStore.safeError(error) }
    }
    private func clearForm() {
        rationale = ""; sourceRef = ""; occurredAt = Date(); draft = nil
    }

    var body: some View {
        Section("Подготовка, подача и результат") {
            Button("Обновить журнал") { Task { await reload() } }.disabled(store.isBusy)
            if let state {
                if let latest = state.latest {
                    LabeledContent("Состояние", value: latest.stage.title)
                    Text(latest.attestation.rationale)
                    if latest.readinessStale { Text("Готовность устарела").foregroundStyle(.orange) }
                } else { Text("Записей пока нет") }
                if canWrite && !state.options.isEmpty {
                    Picker("Состояние", selection: $stage) {
                        ForEach(state.options) { option in Text(option.title + (state.latest?.stage.isOutcome == true ? " (исправление)" : "")).tag(option) }
                    }
                    TextField("Обоснование", text: $rationale, axis: .vertical).lineLimit(3...6)
                    if !stage.isPreparation {
                        TextField("Номер квитанции или ссылка на протокол", text: $sourceRef)
                        DatePicker("Дата события", selection: $occurredAt, in: ...Date())
                    }
                    Button("Проверить и подтвердить запись") {
                        do {
                            draft = try CompanyLifecycleDraft(stage: stage, rationale: rationale, sourceRef: stage.isPreparation ? nil : sourceRef,
                                                              occurredAt: stage.isPreparation ? nil : occurredAt, state: state)
                            confirm = true
                        } catch { notice = CompanyStore.safeError(error) }
                    }.disabled(store.isBusy || rationale.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                Button("История событий") {
                    Task {
                        history = nil
                        do { history = try await store.loadLifecycleHistory(accountID: accountID, item: item) }
                        catch { notice = CompanyStore.safeError(error) }
                    }
                }.disabled(store.isBusy)
                if let history {
                    ForEach(history.items) { event in
                        VStack(alignment: .leading, spacing: 4) {
                            Text("v\(event.revision) · \(event.stage.title)").font(.headline)
                            Text(event.attestation.rationale)
                            if let reference = event.attestation.sourceRef { Text(reference).font(.caption).textSelection(.enabled) }
                            if let date = event.attestation.occurredAt { Text(date.formatted()).font(.caption) }
                        }
                    }
                    if history.hasMore { Text("Первые 50 событий").font(.caption) }
                }
            }
            if let notice { Text(notice).foregroundStyle(.orange).font(.caption) }
            Text("Внутренние записи сотрудника. Квитанции и протоколы независимо не проверены. Это не действие на ЭТП.").font(.caption).foregroundStyle(.secondary)
        }
        .disabled(store.isBusy)
        .alert("Подтвердить запись?", isPresented: $confirm) {
            Button("Сохранить") {
                guard let prepared = draft else { return }
                Task {
                    do {
                        _ = try await store.submitLifecycle(accountID: accountID, item: item, draft: prepared)
                        clearForm(); await reload()
                    } catch {
                        if case CompanyConnectionError.http(409) = error { state = nil; history = nil; draft = nil }
                        notice = CompanyStore.safeError(error)
                    }
                }
            }
            Button("Отмена", role: .cancel) { draft = nil }
        } message: {
            Text("\(store.identity?.companyName ?? "Компания") · \(item.displayReference) · \(draft?.stage.title ?? "—"). Это запись сведений, не подача заявки.")
        }
        .onChange(of: store.selectedID) { _, _ in state = nil; history = nil; clearForm() }
        .onChange(of: store.identity?.memberId) { _, value in if value == nil { state = nil; history = nil; clearForm() } }
    }
}
