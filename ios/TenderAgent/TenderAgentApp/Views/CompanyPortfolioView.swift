import SwiftUI

struct CompanyPortfolioView: View {
    @StateObject private var store = CompanyStore()
    @State private var origin = BackendCredentialStore.defaultBaseURLString
    @State private var token = ""
    @State private var selectedCase: CompanyCase?
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
                Section("Портфель компании") {
                    if store.items.isEmpty { Text("В портфеле пока нет карточек.") }
                    ForEach(store.items) { item in
                        Button { selectedCase = item } label: {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(item.registryNumber ?? "Номер не указан").font(.headline)
                                Text(item.decision?.action ?? "Решение не принято")
                                Text("Ссылка на ЕИС · требуется проверка").font(.caption).foregroundStyle(.secondary)
                            }.foregroundStyle(.primary)
                        }.disabled(store.isBusy)
                    }
                    if store.hasMore { Button("Показать ещё") { Task { await store.nextPage() } }.disabled(store.isBusy) }
                }
            }
        }
        .navigationTitle("Компании")
        .refreshable { await store.refresh() }
        .sheet(item: $selectedCase) { item in CompanyCaseDetail(item: item, store: store) }
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
    @ObservedObject var store: CompanyStore
    @Environment(\.dismiss) private var dismiss
    @State private var evidence: CompanyEvidencePage?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                Section("Закупка") {
                    Text(item.registryNumber ?? "Номер не указан")
                    Text("Идентификатор закупки не подтверждает актуальный правовой статус.").font(.caption).foregroundStyle(.secondary)
                }
                Section("Решение компании") {
                    if let decision = item.decision {
                        LabeledContent("Действие", value: decision.action)
                        Text(decision.rationale)
                        LabeledContent("Версия", value: String(decision.revision))
                        if let due = decision.deferredUntil { Text(due, style: .date) }
                    } else { Text("Решение не принято") }
                    Text("Только просмотр. Отправка заявок недоступна.").font(.caption).foregroundStyle(.secondary)
                }
                if let identity = store.identity, ["owner", "admin", "analyst"].contains(identity.role) {
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
            .task {
                guard let identity = store.identity, ["owner", "admin", "analyst"].contains(identity.role) else { return }
                do { evidence = try await store.evidence(for: item.caseId) }
                catch { self.error = CompanyStore.safeError(error) }
            }
        }
    }
}
