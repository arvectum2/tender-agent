import SwiftUI
import UniformTypeIdentifiers

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
                if let identity = store.identity, identity.legalAccepted, ["owner", "admin", "analyst"].contains(identity.role) {
                    CompanyPriceSection(item: item, accountID: accountID, store: store)
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
                if item.isCommercial, let latest = state.latest, latest.stage == .ready, !latest.readinessStale {
                    CompanyReadyEvidenceView(item: item, accountID: accountID, event: latest, store: store).id(latest.eventId)
                }
                ForEach((history?.items ?? [state.latest].compactMap { $0 }).filter { !$0.stage.isPreparation }) { event in
                    CompanyEventFileView(item: item, accountID: accountID, event: event, store: store).id(event.eventId)
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

private struct CompanyReadyEvidenceView: View {
    let item: CompanyCase
    let accountID: String
    let event: CompanyLifecycleEvent
    @ObservedObject var store: CompanyStore
    @State private var binding: CompanyReadinessBinding?
    @State private var acknowledge = false
    @State private var notice: String?
    private var canWrite: Bool { store.canDecide(accountID: accountID, caseID: item.caseId, revision: item.revision) }
    private func load(bind: CompanyReadinessBinding? = nil) async {
        binding = nil; acknowledge = false; notice = nil
        do { binding = try await store.readiness(accountID: accountID, item: item, event: event, bind: bind) }
        catch { notice = CompanyStore.safeError(error) }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Документальное подтверждение READY").font(.headline)
            Button("Проверить матрицу") { Task { await load() } }.disabled(store.isBusy)
            if let binding {
                Text(binding.bindingCurrent ? "Снимок актуален (частичная проверка)" : binding.bindingId != nil ? "Снимок устарел. Создайте новую запись READY." : binding.canBind ? "Можно связать частичную матрицу с READY" : "Есть нерешённые требования")
                Text("Документов: \(binding.projection.candidateCount); непрозрачных ссылок: \(binding.projection.rejectedOrOpaqueLinks)").font(.caption)
                ForEach(binding.projection.issues, id: \.self) { issue in Text(Self.issueLabels[issue] ?? issue).font(.caption) }
                if canWrite && binding.canBind {
                    Toggle("Подтверждаю частичное покрытие, не полную квалификацию", isOn: $acknowledge)
                    Button("Связать проверку с READY") { Task { await load(bind: binding) } }.disabled(!acknowledge || store.isBusy)
                }
            }
            if let notice { Text(notice).font(.caption).foregroundStyle(.orange) }
            Text("Не означает полного соответствия ТЗ или подтверждения оригиналов ЭТП.").font(.caption).foregroundStyle(.secondary)
        }
        .onChange(of: store.selectedID) { _, _ in binding = nil; acknowledge = false; notice = nil }
        .onChange(of: store.identity?.memberId) { _, value in if value == nil { binding = nil; acknowledge = false; notice = nil } }
    }
    private static let issueLabels = ["ACTIVE_PROFILE_REQUIRED":"Нет активного профиля", "DOCUMENT_BOUND_EXCEEDED":"Превышен лимит документов", "NO_DISCOVERED_DOCUMENTS":"Не обнаружены документы", "MISSING_USER_COPIES":"Нет копий документов", "TRUNCATED_LINK_SCAN":"Поиск ссылок неполный", "DOCUMENT_NOT_REVIEWABLE":"Документ не поддерживается", "UNREVIEWED_FRAGMENT":"Есть непроверенные фрагменты", "STALE_REVIEW":"Оценка устарела", "UNRESOLVED_REQUIREMENT":"Есть нерешённые требования", "NO_RECORDED_SUPPORT":"Нет записанного подтверждения"]
}

private struct CompanyExportDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.data] }
    static var writableContentTypes: [UTType] { CompanyArtifactBytes.formats.compactMap { UTType(filenameExtension: $0) } + [.data] }
    let data: Data
    init(data: Data) { self.data = data }
    init(configuration: ReadConfiguration) throws { throw CompanyConnectionError.invalidArtifact }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: data) }
}

private struct CompanyEventFileView: View {
    let item: CompanyCase
    let accountID: String
    let event: CompanyLifecycleEvent
    @ObservedObject var store: CompanyStore
    @State private var artifact: CompanyEventArtifact?
    @State private var missing = false
    @State private var selected: CompanyArtifactBytes?
    @State private var importing = false
    @State private var acknowledge = false
    @State private var notice: String?
    @State private var export: CompanyExportDocument?
    @State private var exporting = false
    private var canWrite: Bool { store.canDecide(accountID: accountID, caseID: item.caseId, revision: item.revision) }
    private func reset() { artifact = nil; missing = false; selected = nil; acknowledge = false; notice = nil; export = nil; exporting = false; importing = false }
    private func load() async {
        reset()
        do { artifact = try await store.eventArtifact(accountID: accountID, item: item, event: event) }
        catch CompanyConnectionError.http(404) { missing = true; notice = "Копия не найдена или функция отключена." }
        catch { notice = CompanyStore.safeError(error) }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("v\(event.revision) · \(event.stage == .submitted ? "Квитанция" : "Протокол")").font(.headline)
            Button("Проверить файл события") { Task { await load() } }.disabled(store.isBusy)
            if let artifact {
                Text("\(artifact.formatHint.uppercased()) · \(artifact.inspection.sizeBytes) байт")
                Text(artifact.inspection.sha256).font(.caption2).textSelection(.enabled)
                Button("Скачать проверенную копию") {
                    Task {
                        export = nil; notice = nil
                        do {
                            let bytes = try await store.downloadEventArtifact(accountID: accountID, item: item, event: event, artifact: artifact)
                            guard store.selectedID == accountID, store.identity != nil else { return }
                            export = CompanyExportDocument(data: bytes.data); exporting = true
                        } catch { notice = CompanyStore.safeError(error) }
                    }
                }.disabled(store.isBusy)
            } else if missing && canWrite {
                Button("Выбрать PDF, DOCX или XLSX") { importing = true }.disabled(store.isBusy)
                if let selected {
                    Text("\(selected.format.uppercased()) · \(selected.data.count) байт")
                    Toggle("Копия сотрудника, происхождение на ЭТП не проверено", isOn: $acknowledge)
                    Button("Сохранить файл события") {
                        acknowledge = false; notice = nil
                        Task {
                            do { artifact = try await store.eventArtifact(accountID: accountID, item: item, event: event, upload: selected); self.selected = nil; missing = false }
                            catch { notice = CompanyStore.safeError(error) }
                        }
                    }.disabled(!acknowledge || store.isBusy)
                }
            }
            if let notice { Text(notice).font(.caption).foregroundStyle(.orange) }
            Text("Подлинность и электронная подпись не проверены.").font(.caption).foregroundStyle(.secondary)
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: CompanyArtifactBytes.formats.compactMap { UTType(filenameExtension: $0) }) { result in
            selected = nil; acknowledge = false
            do { guard canWrite else { return }; selected = try CompanyArtifactBytes.read(result.get()) }
            catch { notice = CompanyStore.safeError(error) }
        }
        .fileExporter(isPresented: $exporting, document: export, contentType: artifact.flatMap { UTType(filenameExtension: $0.formatHint) } ?? .data, defaultFilename: artifact?.filename ?? "lifecycle") { result in
            export = nil
            if case .failure(let error) = result { notice = CompanyStore.safeError(error) }
        }
        .onChange(of: exporting) { _, value in if !value { export = nil } }
        .onChange(of: store.selectedID) { _, _ in reset() }
        .onChange(of: store.identity?.memberId) { _, value in if value == nil { reset() } }
    }
}

private struct CompanyPriceSection: View {
    let item: CompanyCase
    let accountID: String
    @ObservedObject var store: CompanyStore
    @State private var input = CompanyPriceInput()
    @State private var itemizedMode = false
    @State private var lines: [CompanyCostLine] = []
    @State private var line = CompanyCostLine()
    @State private var editingIndex: Int?
    @State private var zeroCategories: Set<CompanyCostCategory> = []
    @State private var noDoubleCount = false
    @State private var projection: CompanyItemizedProjection?
    @State private var manual = ""
    @State private var ceiling = ""
    @State private var preview: CompanyPriceResult?
    @State private var previewInput: CompanyPriceInput?
    @State private var history: [CompanyPriceRecord]?
    @State private var pending: CompanyPriceAttempt?
    @State private var confirmSave = false
    @State private var notice: String?
    @State private var selectedVersion: String = ""

    private var canSave: Bool { store.canDecide(accountID: accountID,caseID:item.caseId,revision:item.revision) }
    private var draft: CompanyPriceInput {
        var value = input
        value.externalDirectRub = CompanyPriceInput.normalize(value.externalDirectRub)
        value.ownLaborRub = CompanyPriceInput.normalize(value.ownLaborRub)
        value.cashOverheadRub = CompanyPriceInput.normalize(value.cashOverheadRub)
        value.reserveRub = CompanyPriceInput.normalize(value.reserveRub)
        value.fixedPlatformFeesRub = CompanyPriceInput.normalize(value.fixedPlatformFeesRub)
        value.guaranteeFinancingCostRub = CompanyPriceInput.normalize(value.guaranteeFinancingCostRub)
        value.revenueTaxPercent = CompanyPriceInput.normalize(value.revenueTaxPercent)
        value.variablePlatformFeePercent = CompanyPriceInput.normalize(value.variablePlatformFeePercent)
        value.minimumProfitRub = CompanyPriceInput.normalize(value.minimumProfitRub)
        value.targetProfitRub = CompanyPriceInput.normalize(value.targetProfitRub)
        let limit = CompanyPriceInput.normalize(ceiling)
        value.referenceCeilingRub = limit.isEmpty ? nil : limit
        value.manualBidPricesRub = manual.components(separatedBy: .newlines).map(CompanyPriceInput.normalize).filter { !$0.isEmpty }
        value.assumptionNote = value.assumptionNote.trimmingCharacters(in:.whitespacesAndNewlines)
        return value
    }
    private var lineDirty: Bool { editingIndex != nil || line != CompanyCostLine() }
    private var estimate: CompanyItemizedInput {
        .init(lines:lines,zeroCostCategories:CompanyCostCategory.allCases.filter { zeroCategories.contains($0) },terms:CompanyPriceTerms(draft),confirmNoDoubleCount:noDoubleCount)
    }
    private var previewCurrent: Bool {
        guard let value=previewInput else { return false }
        return itemizedMode ? !lineDirty && projection?.inputs == estimate : projection == nil && value == draft
    }
    private func finishLine() { editingIndex=nil; line=CompanyCostLine() }
    private func lineChanged() { noDoubleCount=false; invalidate() }
    private func saveLine() {
        let value=line.normalized
        guard value.amount != nil else { notice="Заполните строку: положительное количество и ставка, единица и источник."; return }
        if let index=editingIndex, lines.indices.contains(index) { lines[index]=value }
        else { guard editingIndex==nil, lines.count<60 else { return }; lines.append(value) }
        zeroCategories.remove(value.category); finishLine(); lineChanged()
    }
    private func invalidate() { projection = nil; preview = nil; previewInput = nil; pending = nil; confirmSave = false; notice = nil }
    private func reset() { invalidate(); itemizedMode=false; lines=[]; finishLine(); zeroCategories=[]; noDoubleCount=false; input = CompanyPriceInput(); manual = ""; ceiling = ""; history = nil; selectedVersion = "" }
    private func calculate() async {
        invalidate()
        do {
            if itemizedMode {
                guard !lineDirty else { notice="Сохраните или отмените текущую строку."; return }
                let value=estimate
                guard value.sums != nil else { notice="Заполните смету, отметьте нулевые категории и подтвердите отсутствие двойного учёта."; return }
                let response=try await store.itemizedPreview(accountID:accountID,item:item,estimate:value)
                guard store.selectedID==accountID, store.identity != nil, itemizedMode, estimate==value, !lineDirty else { return }
                projection=response.itemizedEstimate; preview=response.result; previewInput=response.inputs
            } else {
                let value=draft
                guard value.valid else { notice=CompanyConnectionError.invalidPrice.localizedDescription; return }
                let response=try await store.pricePreview(accountID:accountID,item:item,input:value)
                guard store.selectedID==accountID, store.identity != nil, !itemizedMode, draft==value else { return }
                preview=response.result; previewInput=value
            }
            notice="Предварительный расчёт, не сохранён."
        } catch { notice=CompanyStore.safeError(error) }
    }
    private func loadHistory() async {
        history = nil; pending = nil; selectedVersion = ""; notice = nil
        do { history = try await store.priceHistory(accountID:accountID,item:item).items }
        catch { notice = CompanyStore.safeError(error) }
    }
    private func prepareSave() {
        guard canSave, let result = preview, let value = previewInput, previewCurrent, let history else { return }
        do {
            pending = try CompanyPriceAttempt.prepare(previous:pending,accountID:accountID,caseID:item.caseId,revision:history.first?.revision ?? 0,input:value,result:result,itemized:projection)
            confirmSave = true
        } catch { notice = CompanyStore.safeError(error) }
    }
    private func save() async {
        guard canSave, let attempt = pending, previewCurrent, attempt.payload.scenario == previewInput, attempt.itemized == projection, attempt.preview == preview else { return }
        do {
            let row = try await store.savePrice(accountID:accountID,item:item,attempt:attempt)
            history = [row] + (history ?? []); selectedVersion = row.id
            invalidate(); notice = "Версия v\(row.revision) сохранена. Не утверждение ставки."
        } catch {
            if case CompanyConnectionError.http(409) = error { invalidate(); history = nil; selectedVersion = ""; notice = "Версия изменилась. Обновите историю и пересчитайте." }
            else { notice = CompanyStore.safeError(error) }
        }
    }

    private func amount(_ title: String, _ value: Binding<String>) -> some View {
        TextField(title,text:value).keyboardType(.decimalPad)
    }
    @ViewBuilder private func comparison(_ result: CompanyPriceResult) -> some View {
        LabeledContent("Расходы и резерв",value:result.cashFixedAndReservedRub + " ₽")
        LabeledContent("Полная себестоимость",value:result.fullEconomicCostBeforeRevenueRatesRub + " ₽")
        ForEach(result.scenarios) { row in
            VStack(alignment:.leading,spacing:4) {
                Text(row.title).font(.headline)
                LabeledContent("Цена",value:row.priceRub + " ₽")
                LabeledContent("Денежный остаток",value:row.cashSurplusRub + " ₽")
                LabeledContent("Экономическая прибыль",value:row.economicProfitRub + " ₽")
                LabeledContent("Маржа",value:row.economicMarginPercent.map { $0 + "%" } ?? "—")
                if let within = row.withinUserReferenceCeiling { Text(within ? "В пределах заданной цены" : "Выше заданного предела").font(.caption) }
            }
        }
    }

    @ViewBuilder private func itemizedDetail(_ value: CompanyItemizedProjection) -> some View {
        Text("Постатейная смета · проверка сумм").font(.headline)
        ForEach(value.lines) { row in
            VStack(alignment:.leading,spacing:3) {
                Text("\(row.ordinal). \(row.title)").font(.headline)
                Text(row.category.title).font(.caption)
                Text("\(row.quantity) \(row.unit) × \(row.rateRub) ₽ = \(row.amountRub) ₽").font(.subheadline)
                Text(row.sourceKind.title + ": " + row.sourceNote).font(.caption).textSelection(.enabled)
            }
        }
        ForEach(CompanyCostCategory.allCases) { category in
            LabeledContent(category.title,value:(value.categoryTotalsRub[category.rawValue] ?? "—") + " ₽")
        }
        Text("Округление каждой строки вверх до копейки. Источники заявлены сотрудником, независимой проверки нет.").font(.caption).foregroundStyle(.secondary)
    }
    @ViewBuilder private func editor() -> some View {
        DisclosureGroup("Постатейная смета · \(lines.count)/60") {
            ForEach(lines.indices,id:\.self) { index in
                VStack(alignment:.leading,spacing:3) {
                    Text(lines[index].title).font(.headline)
                    Text(lines[index].category.title + " · " + lines[index].quantity + " " + lines[index].unit + " × " + lines[index].rateRub + " ₽").font(.caption)
                    HStack {
                        Button("Изменить") { editingIndex=index; line=lines[index]; lineChanged() }.buttonStyle(.borderless).disabled(lineDirty)
                        Button("Удалить",role:.destructive) { lines.remove(at:index); lineChanged() }.buttonStyle(.borderless).disabled(lineDirty)
                    }
                }
            }
            Picker("Категория",selection:$line.category) { ForEach(CompanyCostCategory.allCases) { Text($0.title).tag($0) } }
            TextField("Наименование",text:$line.title)
            TextField("Единица измерения",text:$line.unit)
            amount("Количество",$line.quantity)
            amount("Ставка, ₽",$line.rateRub)
            Picker("Источник",selection:$line.sourceKind) { ForEach(CompanyCostSource.allCases) { Text($0.title).tag($0) } }
            TextField("Обоснование ставки",text:$line.sourceNote,axis:.vertical).lineLimit(2...4)
            Button(editingIndex==nil ? "Добавить строку" : "Сохранить строку") { saveLine() }.disabled(editingIndex==nil && lines.count>=60)
            Button("Отменить редактирование") { finishLine(); lineChanged() }.disabled(!lineDirty)
            ForEach(CompanyCostCategory.allCases) { category in
                if !lines.contains(where:{ $0.category==category }) {
                    Toggle(category.title + ": 0 ₽",isOn:Binding(get:{ zeroCategories.contains(category) },set:{ checked in
                        if checked { zeroCategories.insert(category) } else { zeroCategories.remove(category) }; lineChanged()
                    }))
                }
            }
            Toggle("Подтверждаю отсутствие двойного учёта",isOn:$noDoubleCount)
        }
    }

    var body: some View {
        Section("Экономика предложения · PRICE-01") {
            Text("Заполните все обязательные поля, включая явные нули. Не учитывайте расходы дважды. Сценарные допущения, не налоговый расчёт и не прогноз победы.").font(.caption).foregroundStyle(.secondary)
            Picker("Режим расчёта",selection:$itemizedMode) { Text("Итоговые суммы").tag(false); Text("Постатейная смета").tag(true) }
            if itemizedMode { editor() }
            DisclosureGroup("Себестоимость и ставки") {
                if !itemizedMode {
                amount("Прямые расходы, ₽",$input.externalDirectRub)
                amount("Дополнительная стоимость собственного труда, ₽",$input.ownLaborRub)
                amount("Денежные накладные расходы, ₽",$input.cashOverheadRub)
                amount("Резерв риска, ₽",$input.reserveRub)
                amount("Фиксированные сборы ЭТП, ₽",$input.fixedPlatformFeesRub)
                amount("Стоимость финансирования и гарантий, ₽",$input.guaranteeFinancingCostRub)
                }
                Text("Учитывайте стоимость финансирования, не сумму обеспечения.").font(.caption).foregroundStyle(.secondary)
                amount("Налог от выручки, %",$input.revenueTaxPercent)
                amount("Переменная комиссия, %",$input.variablePlatformFeePercent)
                amount("Минимальная прибыль, ₽",$input.minimumProfitRub)
                amount("Целевая прибыль, ₽",$input.targetProfitRub)
                amount("Предел цены, ₽ (необязательно)",$ceiling)
                TextField("До 8 цен, каждая с новой строки",text:$manual,axis:.vertical).lineLimit(2...8)
                TextField("Источники и обоснование допущений",text:$input.assumptionNote,axis:.vertical).lineLimit(3...8)
                Toggle("Подтверждаю сценарные допущения, не утверждённую цену",isOn:$input.acceptHypotheticalAssumptionsOnly)
            }
            Button("Рассчитать") { Task { await calculate() } }.disabled(store.isBusy || !input.acceptHypotheticalAssumptionsOnly)
            Button("Загрузить историю расчётов") { Task { await loadHistory() } }.disabled(store.isBusy)
            if let preview {
                if let projection { itemizedDetail(projection) }
                comparison(preview)
                if canSave {
                    Button("Проверить и сохранить версию") { prepareSave() }.disabled(store.isBusy || history == nil || (history?.first?.revision ?? 0) >= 30)
                    if history == nil { Text("Для сохранения загрузите историю.").font(.caption).foregroundStyle(.secondary) }
                }
            }
            if let history {
                if history.isEmpty { Text("Сохранённых версий нет.").font(.caption) }
                else {
                    Picker("Версия",selection:$selectedVersion) {
                        Text("Выберите версию").tag("")
                        ForEach(history) { row in Text("v\(row.revision) · \(row.itemizedEstimate == nil ? "Итоги" : "Смета") · \(row.createdAt.formatted(date:.abbreviated,time:.shortened))").tag(row.id) }
                    }
                    if let row = history.first(where: { $0.id == selectedVersion }) {
                        DisclosureGroup("Сохранённые допущения и результаты") {
                            Text(row.inputs.assumptionNote).textSelection(.enabled)
                            LabeledContent("Прямые расходы", value:row.inputs.externalDirectRub + " ₽")
                            LabeledContent("Собственный труд", value:row.inputs.ownLaborRub + " ₽")
                            LabeledContent("Накладные расходы", value:row.inputs.cashOverheadRub + " ₽")
                            LabeledContent("Резерв", value:row.inputs.reserveRub + " ₽")
                            LabeledContent("Сборы ЭТП", value:row.inputs.fixedPlatformFeesRub + " ₽")
                            LabeledContent("Финансирование", value:row.inputs.guaranteeFinancingCostRub + " ₽")
                            LabeledContent("Налог", value:row.inputs.revenueTaxPercent + "%")
                            LabeledContent("Комиссия", value:row.inputs.variablePlatformFeePercent + "%")
                            LabeledContent("Минимальная прибыль", value:row.inputs.minimumProfitRub + " ₽")
                            LabeledContent("Целевая прибыль", value:row.inputs.targetProfitRub + " ₽")
                            LabeledContent("Предел цены", value:row.inputs.referenceCeilingRub.map { $0 + " ₽" } ?? "Не задан")
                            if let detail=row.itemizedEstimate {
                                itemizedDetail(detail)
                                CompanyCostDocumentsView(item:item,accountID:accountID,scenario:row,store:store).id(row.id)
                                CompanyActualView(item:item,accountID:accountID,baseline:.init(scenario:row),store:store).id(row.id)
                            }
                            comparison(row.result)
                        }
                    }
                }
            }
            if let notice { Text(notice).font(.caption).foregroundStyle(.secondary) }
        }
        .disabled(store.isBusy)
        .alert("Сохранить версию расчёта?",isPresented:$confirmSave) {
            Button("Сохранить") { Task { await save() } }
            Button("Отмена",role:.cancel) {}
        } message: {
            Text("\(store.identity?.companyName ?? "Компания") · \(item.displayReference). Это внутренняя оценка, не утверждение цены и не подача заявки.")
        }
        .onChange(of:itemizedMode) { _,_ in invalidate() }
        .onChange(of:line) { _,_ in lineChanged() }
        .onChange(of:noDoubleCount) { _,_ in invalidate() }
        .onChange(of:input) { _,_ in invalidate() }
        .onChange(of:manual) { _,_ in invalidate() }
        .onChange(of:ceiling) { _,_ in invalidate() }
        .onChange(of:store.selectedID) { _,_ in reset() }
        .onChange(of:store.identity?.memberId) { _,value in if value == nil { reset() } }
    }
}

private struct CompanyCostDocumentsView: View {
    let item: CompanyCase
    let accountID: String
    let scenario: CompanyPriceRecord
    @ObservedObject var store: CompanyStore
    @State private var ordinal = 0
    var body: some View {
        if let estimate=scenario.itemizedEstimate {
            DisclosureGroup("Документы сохранённой сметы v\(scenario.revision)") {
                Text("Одна копия на строку, без замены. Подлинность, сумма и оплата независимо не проверены.").font(.caption).foregroundStyle(.secondary)
                Picker("Позиция",selection:$ordinal) {
                    Text("Выберите строку").tag(0)
                    ForEach(estimate.lines) { line in Text("\(line.ordinal). \(line.title) · \(line.amountRub) ₽").tag(line.ordinal) }
                }
                if let line=estimate.lines.first(where:{$0.ordinal==ordinal}) {
                    CompanyCostDocumentView(item:item,accountID:accountID,target:.init(scenario:scenario,line:line),store:store).id(line.ordinal)
                }
            }
            .onChange(of:store.selectedID) { _,_ in ordinal=0 }
            .onChange(of:store.identity?.memberId) { _,_ in ordinal=0 }
        }
    }
}

private struct CompanyCostDocumentView: View {
    let item: CompanyCase
    let accountID: String
    let target: CompanyCostTarget
    @ObservedObject var store: CompanyStore
    @State private var binding: CompanyCostBinding?
    @State private var evidence: CompanyCostEvidence?
    @State private var kind: CompanyCostDocumentKind?
    @State private var bytes: CompanyArtifactBytes?
    @State private var acknowledge=false
    @State private var importing=false
    @State private var exporting=false
    @State private var export: CompanyExportDocument?
    @State private var notice: String?
    @State private var generation=UUID()
    private var canWrite: Bool { store.canDecide(accountID:accountID,caseID:item.caseId,revision:item.revision) }
    private func active(_ g: UUID) -> Bool {
        guard g==generation,store.selectedID==accountID,let identity=store.identity,identity.legalAccepted,["owner","admin","analyst"].contains(identity.role) else { return false }
        return target.matches(identity,caseID:item.caseId)
    }
    private func reset() {
        generation=UUID(); binding=nil; evidence=nil; kind=nil; bytes=nil; acknowledge=false; importing=false; exporting=false; export=nil; notice=nil
    }
    private func load() async {
        reset(); let g=generation
        do {
            let result=try await store.costBinding(accountID:accountID,item:item,target:target)
            guard active(g) else { return }; binding=result; evidence=result.evidence
            notice=result.evidence==nil ? "Копия не приложена к этой строке." : "Копия сохранена. Проверена целостность байтов, не стоимость или оплата."
        } catch CompanyConnectionError.http(404) { if active(g) { notice="Функция недоступна или строка не найдена." } }
        catch { if active(g) { notice=CompanyStore.safeError(error) } }
    }
    private func save() async {
        guard canWrite, acknowledge, let binding, binding.evidence==nil, evidence==nil, let kind, let bytes else { return }
        acknowledge=false; notice=nil; let g=generation
        do {
            let result=try await store.saveCostEvidence(accountID:accountID,item:item,target:target,binding:binding,kind:kind,bytes:bytes)
            guard active(g) else { return }; evidence=result; self.bytes=nil; notice="Копия сохранена. Подлинность, сумма и оплата не проверены."
        } catch CompanyConnectionError.http(409) {
            if active(g) { reset(); notice="Привязка изменилась или документ уже приложен. Проверьте строку повторно." }
        } catch { if active(g) { notice="Запись не подтверждена. Проверьте строку или повторите тот же файл и вид документа. " + CompanyStore.safeError(error) } }
    }
    private func download() async {
        guard let evidence else { return }; export=nil; notice=nil; let g=generation
        do {
            let result=try await store.downloadCostEvidence(accountID:accountID,item:item,target:target,evidence:evidence)
            guard active(g), self.evidence==evidence else { return }
            export=CompanyExportDocument(data:result.data); exporting=true
        } catch { if active(g) { notice=CompanyStore.safeError(error) } }
    }
    var body: some View {
        VStack(alignment:.leading,spacing:8) {
            Text("v\(target.scenario.revision) · строка \(target.line.ordinal) · \(target.line.amountRub) ₽").font(.caption)
            Button("Проверить документ") { Task { await load() } }.disabled(store.isBusy)
            if let evidence {
                Text(evidence.documentKind.title + " · " + evidence.formatHint.uppercased() + " · \(evidence.inspection.sizeBytes) байт")
                Text(evidence.inspection.sha256).font(.caption2).textSelection(.enabled)
                Button("Скачать проверенные байты") { Task { await download() } }.disabled(store.isBusy)
            } else if binding != nil && canWrite {
                Picker("Вид документа",selection:$kind) {
                    Text("Выберите вид").tag(CompanyCostDocumentKind?.none)
                    ForEach(CompanyCostDocumentKind.allCases) { Text($0.title).tag(Optional($0)) }
                }
                Button("Выбрать PDF, DOCX или XLSX (до 2 МБ)") { importing=true }.disabled(store.isBusy)
                if let bytes { Text("\(bytes.format.uppercased()) · \(bytes.data.count) байт").font(.caption) }
                Toggle("Привязать пользовательскую копию без возможности замены. Источник и сумма не проверены.",isOn:$acknowledge)
                Button("Прикрепить документ") { Task { await save() } }.disabled(store.isBusy || !acknowledge || bytes==nil || kind==nil)
            }
            if let notice { Text(notice).font(.caption).foregroundStyle(.secondary) }
        }
        .fileImporter(isPresented:$importing,allowedContentTypes:CompanyArtifactBytes.formats.compactMap { UTType(filenameExtension:$0) }) { result in
            self.bytes=nil; acknowledge=false
            do { guard canWrite,binding != nil,evidence==nil,active(generation) else { return }; bytes=try CompanyArtifactBytes.read(result.get()) }
            catch { notice=CompanyStore.safeError(error) }
        }
        .fileExporter(isPresented:$exporting,document:export,contentType:evidence.flatMap { UTType(filenameExtension:$0.formatHint) } ?? .data,defaultFilename:evidence?.filename ?? "cost") { result in
            export=nil
            if case .failure(let error)=result { notice=CompanyStore.safeError(error) }
        }
        .onChange(of:exporting) { _,value in if !value { export=nil } }
        .onChange(of:kind) { _,_ in acknowledge=false }
        .onChange(of:store.selectedID) { _,_ in reset() }
        .onChange(of:store.identity?.memberId) { _,_ in reset() }
        .onChange(of:store.identity?.role) { _,_ in reset() }
        .onDisappear { reset() }
    }
}

private struct CompanyActualView:View {
    let item:CompanyCase;let accountID:String;let baseline:CompanyActualBaseline
    @ObservedObject var store:CompanyStore
    @State private var history:[CompanyActualRecord]?
    @State private var observations:[CompanyActualObservation]=[]
    @State private var extras:[CompanyCostLine]=[]
    @State private var ordinal=0
    @State private var quantity=""
    @State private var rate=""
    @State private var source=""
    @State private var extra=CompanyCostLine(sourceKind:.actual)
    @State private var date=Date()
    @State private var note=""
    @State private var cumulative=false
    @State private var noDouble=false
    @State private var confirmSave=false
    @State private var preview:CompanyActualResult?
    @State private var previewInput:CompanyActualInput?
    @State private var attempt:CompanyActualAttempt?
    @State private var selected=""
    @State private var notice:String?
    @State private var generation=UUID()
    private var lines:[CompanyProjectedCostLine] {baseline.scenario.itemizedEstimate?.lines ?? []}
    private var canSave:Bool {store.canDecide(accountID:accountID,caseID:item.caseId,revision:item.revision)}
    private var dateString:String {
        let f=DateFormatter();f.calendar=Calendar(identifier:.gregorian);f.locale=Locale(identifier:"en_US_POSIX");f.timeZone=TimeZone(secondsFromGMT:0);f.dateFormat="yyyy-MM-dd";return f.string(from:date)
    }
    private var input:CompanyActualInput? {
        guard let digest=try? baseline.digest() else {return nil}
        return .init(baselineSha256:digest,asOf:dateString,observations:observations,unplannedCosts:extras,note:note.trimmingCharacters(in:.whitespacesAndNewlines),confirmCumulativeUserReport:cumulative,confirmNoDoubleCount:noDouble)
    }
    private var lineDirty:Bool {let old=observations.first{$0.ordinal==ordinal};return quantity != (old?.quantity ?? "") || rate != (old?.rateRub ?? "") || source != (old?.sourceNote ?? "")}
    private var extraDirty:Bool {extra != CompanyCostLine(sourceKind:.actual)}
    private func invalidate(){preview=nil;previewInput=nil;attempt=nil;confirmSave=false;notice=nil}
    private func changed(){invalidate();noDouble=false}
    private func reset(){generation=UUID();history=nil;observations=[];extras=[];ordinal=0;quantity="";rate="";source="";extra=CompanyCostLine(sourceKind:.actual);date=Date();note="";cumulative=false;noDouble=false;selected="";invalidate()}
    private func active(_ g:UUID)->Bool {guard g==generation,store.selectedID==accountID,let identity=store.identity,identity.legalAccepted,["owner","admin","analyst"].contains(identity.role) else{return false};return baseline.scenario.matches(identity,caseID:item.caseId)}
    private func selectLine(_ next:Int){guard !lineDirty else {notice="Сохраните или снимите наблюдение перед сменой строки.";return};ordinal=next;fillLine()}
    private func fillLine(){let old=observations.first{$0.ordinal==ordinal};quantity=old?.quantity ?? "";rate=old?.rateRub ?? "";source=old?.sourceNote ?? ""}
    private func storeLine(){guard lines.contains(where:{$0.ordinal==ordinal}) else{return};let o=CompanyActualObservation(ordinal:ordinal,quantity:CompanyPriceInput.normalize(quantity),rateRub:CompanyPriceInput.normalize(rate),sourceNote:source.trimmingCharacters(in:.whitespacesAndNewlines));guard o.amount != nil else {notice="Укажите количество, ставку и источник; при нулевом количестве ставка 0.";return};observations.removeAll{$0.ordinal==ordinal};observations.append(o);observations.sort{$0.ordinal<$1.ordinal};fillLine();changed()}
    private func clearLine(){observations.removeAll{$0.ordinal==ordinal};fillLine();changed()}
    private func addExtra(){let value=extra.normalized;guard extras.count<30,value.amount != nil else {notice="Заполните положительное количество, ставку и источник.";return};extras.append(value);extra=CompanyCostLine(sourceKind:.actual);changed()}
    private func load() async {reset();let g=generation;do {let rows=try await store.actualHistory(accountID:accountID,item:item,baseline:baseline);guard active(g) else{return};history=rows;notice="Новый накопительный срез. Прошлые значения не переносятся автоматически."} catch CompanyConnectionError.http(404) {if active(g){notice="Функция недоступна или смета не найдена."}} catch {if active(g){notice=CompanyStore.safeError(error)}}}
    private func calculate() async {invalidate();guard !lineDirty,!extraDirty,let input,input.valid(baseline) else {notice="Завершите ввод строк, укажите дату, обоснование и подтверждения.";return};let g=generation;do{let result=try await store.actualPreview(accountID:accountID,item:item,baseline:baseline,input:input);guard active(g),self.input==input,!lineDirty,!extraDirty else{return};preview=result.result;previewInput=input;notice="Предварительный расчёт, не сохранён."}catch{if active(g){notice=CompanyStore.safeError(error)}}}
    private func prepare(){guard canSave,let history,let preview,let input,input==previewInput,!lineDirty,!extraDirty else{return};do{attempt=try CompanyActualAttempt.prepare(previous:attempt,accountID:accountID,baseline:baseline,revision:history.first?.revision ?? 0,input:input,result:preview);confirmSave=true}catch{notice=CompanyStore.safeError(error)}}
    private func save() async {guard canSave,let attempt,attempt.payload.snapshot==input,attempt.result==preview,!lineDirty,!extraDirty else{return};let g=generation;do{let row=try await store.saveActual(accountID:accountID,item:item,baseline:baseline,attempt:attempt);guard active(g) else{return};history=[row]+(history ?? []);selected=row.id;invalidate();notice="Срез v\(row.revision) сохранён. Не подтверждение оплаты."}catch CompanyConnectionError.http(409){if active(g){reset();notice="Версия или дата конфликтует. Загрузите историю и пересчитайте."}}catch{if active(g){notice="Запись не подтверждена. Повторите тот же срез или проверьте историю. "+CompanyStore.safeError(error)}}}
    @ViewBuilder private func comparison(_ r:CompanyActualResult)->some View {
        Text("На \(r.asOf) · пользовательские данные").font(.headline)
        LabeledContent("План",value:r.totals.plannedRub+" ₽")
        LabeledContent("Заявлено",value:r.totals.reportedTotalRub+" ₽")
        LabeledContent("Внеплановые",value:r.totals.reportedUnplannedRub+" ₽")
        Text("Незаявленных строк: \(r.totals.missingPlannedLines)")
        if let delta=r.totals.reportedVsFullPlanRub {LabeledContent("Отклонение от сметы",value:delta+" ₽")} else {Text("Отклонение от всей сметы не рассчитано.").font(.caption)}
        ForEach(r.lines){row in VStack(alignment:.leading,spacing:3){Text(row.title).font(.headline);LabeledContent("План",value:row.plannedAmountRub+" ₽");LabeledContent("Факт",value:row.actualAmountRub.map{$0+" ₽"} ?? "Не заявлено");if let d=row.varianceRub {LabeledContent("Отклонение",value:d+" ₽ · "+(row.variancePercent ?? "—")+"%")};if let source=row.sourceNote {Text(source).font(.caption)}}}
        ForEach(r.unplannedCosts){row in VStack(alignment:.leading){Text("Вне плана: "+row.title);Text(row.quantity+" "+row.unit+" × "+row.rateRub+" ₽ = "+row.actualAmountRub+" ₽");Text(row.sourceNote).font(.caption)}}
        DisclosureGroup("Итоги по категориям") {ForEach(CompanyCostCategory.allCases){cat in if let t=r.categoryTotals[cat.rawValue]{VStack(alignment:.leading){Text(cat.title).font(.headline);LabeledContent("План",value:t.plannedRub+" ₽");LabeledContent("Заявлено",value:t.reportedTotalRub+" ₽");LabeledContent("Внеплановые",value:t.reportedUnplannedRub+" ₽");Text("Незаявлено строк: \(t.missingPlannedLines)");LabeledContent("Отклонение сопоставимых строк",value:t.matchedVarianceRub.map{$0+" ₽"} ?? "—")}}}}
        Text("Полнота затрат договора, подлинность сумм, оплата и прибыль не подтверждены.").font(.caption).foregroundStyle(.secondary)
    }
    @ViewBuilder private func editor()->some View {
        DatePicker("Дата среза (UTC)",selection:$date,in:...Date(),displayedComponents:.date).environment(\.timeZone,TimeZone(secondsFromGMT:0)!)
        Picker("Плановая строка",selection:Binding(get:{ordinal},set:selectLine)){Text("Выберите строку").tag(0);ForEach(lines){l in Text("\(l.ordinal). "+l.title).tag(l.ordinal)}}
        if let l=lines.first(where:{$0.ordinal==ordinal}) {
            Text("План: \(l.quantity) \(l.unit) × \(l.rateRub) ₽")
            TextField("Фактическое количество",text:$quantity).keyboardType(.decimalPad)
            TextField("Фактическая ставка, ₽",text:$rate).keyboardType(.decimalPad)
            TextField("Источник факта",text:$source)
            Button("Записать факт строки"){storeLine()}.buttonStyle(.borderless)
            Button("Снять наблюдение"){clearLine()}.buttonStyle(.borderless)
        }
        ForEach(lines){l in LabeledContent(l.title,value:observations.first(where:{$0.ordinal==l.ordinal}).map{$0.quantity+" "+l.unit+" × "+$0.rateRub+" ₽"} ?? "Не заявлено")}
        DisclosureGroup("Внеплановые расходы · \(extras.count)/30") {
            ForEach(extras.indices,id:\.self){i in VStack(alignment:.leading){Text(extras[i].title);Text(extras[i].quantity+" "+extras[i].unit+" × "+extras[i].rateRub+" ₽");Button("Удалить",role:.destructive){extras.remove(at:i);changed()}.buttonStyle(.borderless).disabled(extraDirty)}}
            Picker("Категория",selection:$extra.category){ForEach(CompanyCostCategory.allCases){Text($0.title).tag($0)}}
            TextField("Наименование",text:$extra.title);TextField("Единица",text:$extra.unit)
            TextField("Количество",text:$extra.quantity).keyboardType(.decimalPad);TextField("Ставка, ₽",text:$extra.rateRub).keyboardType(.decimalPad)
            TextField("Источник",text:$extra.sourceNote)
            Button("Добавить расход"){addExtra()}.disabled(extras.count>=30)
            Button("Очистить черновик"){extra=CompanyCostLine(sourceKind:.actual);changed()}.disabled(!extraDirty)
        }
        TextField("Обоснование среза",text:$note,axis:.vertical).lineLimit(2...5)
        Toggle("Подтверждаю накопленный пользовательский факт, не оплату",isOn:$cumulative)
        Toggle("Подтверждаю отсутствие двойного учёта",isOn:$noDouble)
        Button("Рассчитать отклонения"){Task{await calculate()}}.disabled(!cumulative || !noDouble)
    }
    var body:some View {
        DisclosureGroup("План-факт сметы v\(baseline.scenario.revision)") {
            Text("Накопленные расходы на дату. Не суммируйте версии. Незаявленные строки не равны нулю.").font(.caption).foregroundStyle(.secondary)
            Button("Загрузить план и историю факта"){Task{await load()}}
            if let history {
                editor()
                if let preview {comparison(preview);if canSave {Button("Проверить и сохранить срез"){prepare()}.disabled((history.first?.revision ?? 0)>=30)}}
                if !history.isEmpty {Picker("Сохранённый срез",selection:$selected){Text("Выберите срез").tag("");ForEach(history){Text("v\($0.revision) · \($0.inputs.asOf)").tag($0.id)}};if let row=history.first(where:{$0.id==selected}) {DisclosureGroup("Сохранённые результаты"){comparison(row.result);Text(row.inputs.note).textSelection(.enabled)};CompanyActualDocumentsView(item:item,accountID:accountID,baseline:baseline,snapshot:row,store:store).id(row.id)}}
            }
            if let notice {Text(notice).font(.caption).foregroundStyle(.secondary)}
        }
        .disabled(store.isBusy)
        .alert("Сохранить неизменяемый срез?",isPresented:$confirmSave){Button("Сохранить"){Task{await save()}};Button("Отмена",role:.cancel){}} message:{Text("Смета v\(baseline.scenario.revision) · \(dateString). Это пользовательские данные, не подтверждение оплаты.")}
        .onChange(of:quantity){_,_ in if lineDirty {changed()}}
        .onChange(of:rate){_,_ in if lineDirty {changed()}}
        .onChange(of:source){_,_ in if lineDirty {changed()}}
        .onChange(of:extra){_,_ in changed()}
        .onChange(of:date){_,_ in changed()}
        .onChange(of:note){_,_ in changed()}
        .onChange(of:cumulative){_,_ in invalidate()}
        .onChange(of:noDouble){_,_ in invalidate()}
        .onChange(of:store.selectedID){_,_ in reset()}
        .onChange(of:store.identity?.memberId){_,_ in reset()}
        .onChange(of:store.identity?.role){_,_ in reset()}
        .onDisappear{reset()}
    }
}


private struct CompanyActualDocumentsView:View {
    let item:CompanyCase;let accountID:String;let baseline:CompanyActualBaseline;let snapshot:CompanyActualRecord
    @ObservedObject var store:CompanyStore
    @State private var selected=""
    var body:some View {
        DisclosureGroup("Документы фактических затрат v\(snapshot.revision)") {
            Text("Одна пользовательская копия на заявленную строку, без замены. Подлинность, сумма, оплата и исполнение договора не подтверждены.").font(.caption).foregroundStyle(.secondary)
            let rows=CompanyActualEvidenceRow.rows(snapshot)
            Picker("Заявленная позиция",selection:$selected) {
                Text("Выберите строку").tag("");ForEach(rows){Text($0.label).tag($0.id)}
            }
            if let row=rows.first(where:{$0.id==selected}) {
                CompanyActualDocumentView(item:item,accountID:accountID,target:.init(baseline:baseline,snapshot:snapshot,row:row),store:store).id(row.id)
            }
        }
        .onChange(of:store.selectedID){_,_ in selected=""}
        .onChange(of:store.identity?.memberId){_,_ in selected=""}
        .onChange(of:store.identity?.role){_,_ in selected=""}
        .onDisappear{selected=""}
    }
}

private struct CompanyActualDocumentView: View {
    let item: CompanyCase
    let accountID: String
    let target: CompanyActualEvidenceTarget
    @ObservedObject var store: CompanyStore
    @State private var binding: CompanyActualEvidenceBinding?
    @State private var evidence: CompanyActualEvidence?
    @State private var kind: CompanyActualDocumentKind?
    @State private var bytes: CompanyArtifactBytes?
    @State private var acknowledge=false
    @State private var importing=false
    @State private var exporting=false
    @State private var export: CompanyExportDocument?
    @State private var notice: String?
    @State private var generation=UUID()
    private var canWrite: Bool { store.canDecide(accountID:accountID,caseID:item.caseId,revision:item.revision) }
    private func active(_ g: UUID) -> Bool {
        guard g==generation,store.selectedID==accountID,let identity=store.identity,identity.legalAccepted,["owner","admin","analyst"].contains(identity.role) else { return false }
        return target.matches(identity,caseID:item.caseId)
    }
    private func reset() {
        generation=UUID(); binding=nil; evidence=nil; kind=nil; bytes=nil; acknowledge=false; importing=false; exporting=false; export=nil; notice=nil
    }
    private func load() async {
        reset(); let g=generation
        do {
            let result=try await store.actualEvidenceBinding(accountID:accountID,item:item,target:target)
            guard active(g) else { return }; binding=result; evidence=result.evidence
            notice=result.evidence==nil ? "Копия не приложена к этой строке." : "Копия сохранена. Проверена целостность байтов, не стоимость или оплата."
        } catch CompanyConnectionError.http(404) { if active(g) { notice="Функция недоступна или строка не найдена." } }
        catch { if active(g) { notice=CompanyStore.safeError(error) } }
    }
    private func save() async {
        guard canWrite, acknowledge, let binding, binding.evidence==nil, evidence==nil, let kind, let bytes else { return }
        acknowledge=false; notice=nil; let g=generation
        do {
            let result=try await store.saveActualEvidence(accountID:accountID,item:item,target:target,binding:binding,kind:kind,bytes:bytes)
            guard active(g) else { return }; evidence=result; self.bytes=nil; notice="Копия сохранена. Подлинность, сумма и оплата не проверены."
        } catch CompanyConnectionError.http(409) {
            if active(g) { reset(); notice="Привязка изменилась или документ уже приложен. Проверьте строку повторно." }
        } catch { if active(g) { notice="Запись не подтверждена. Проверьте строку или повторите тот же файл и вид документа. " + CompanyStore.safeError(error) } }
    }
    private func download() async {
        guard let evidence else { return }; export=nil; notice=nil; let g=generation
        do {
            let result=try await store.downloadActualEvidence(accountID:accountID,item:item,target:target,evidence:evidence)
            guard active(g), self.evidence==evidence else { return }
            export=CompanyExportDocument(data:result.data); exporting=true
        } catch { if active(g) { notice=CompanyStore.safeError(error) } }
    }
    var body: some View {
        VStack(alignment:.leading,spacing:8) {
            Text("Факт v\(target.snapshot.revision) · \(target.row.label)").font(.caption)
            Button("Проверить документ") { Task { await load() } }.disabled(store.isBusy)
            if let evidence {
                Text(evidence.documentKind.title + " · " + evidence.formatHint.uppercased() + " · \(evidence.inspection.sizeBytes) байт")
                Text(evidence.inspection.sha256).font(.caption2).textSelection(.enabled)
                Button("Скачать проверенные байты") { Task { await download() } }.disabled(store.isBusy)
            } else if binding != nil && canWrite {
                Picker("Вид документа",selection:$kind) {
                    Text("Выберите вид").tag(CompanyActualDocumentKind?.none)
                    ForEach(CompanyActualDocumentKind.allCases) { Text($0.title).tag(Optional($0)) }
                }
                Button("Выбрать PDF, DOCX или XLSX (до 2 МБ)") { importing=true }.disabled(store.isBusy)
                if let bytes { Text("\(bytes.format.uppercased()) · \(bytes.data.count) байт").font(.caption) }
                Toggle("Привязать пользовательскую копию без возможности замены. Источник, сумма и оплата не проверены.",isOn:$acknowledge)
                Button("Прикрепить документ") { Task { await save() } }.disabled(store.isBusy || !acknowledge || bytes==nil || kind==nil)
            }
            if let notice { Text(notice).font(.caption).foregroundStyle(.secondary) }
        }
        .fileImporter(isPresented:$importing,allowedContentTypes:CompanyArtifactBytes.formats.compactMap { UTType(filenameExtension:$0) }) { result in
            self.bytes=nil; acknowledge=false
            do { guard canWrite,binding != nil,evidence==nil,active(generation) else { return }; bytes=try CompanyArtifactBytes.read(result.get()) }
            catch { notice=CompanyStore.safeError(error) }
        }
        .fileExporter(isPresented:$exporting,document:export,contentType:evidence.flatMap { UTType(filenameExtension:$0.formatHint) } ?? .data,defaultFilename:evidence?.filename ?? "actual") { result in
            export=nil
            if case .failure(let error)=result { notice=CompanyStore.safeError(error) }
        }
        .onChange(of:exporting) { _,value in if !value { export=nil } }
        .onChange(of:kind) { _,_ in acknowledge=false }
        .onChange(of:store.selectedID) { _,_ in reset() }
        .onChange(of:store.identity?.memberId) { _,_ in reset() }
        .onChange(of:store.identity?.role) { _,_ in reset() }
        .onDisappear { reset() }
    }
}
