import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: AppStore

    @State private var baseURL = BackendCredentialStore.savedBaseURL
    @State private var username = BackendCredentialStore.savedUsername
    @State private var password = ""

    @State private var reportPush = true
    @State private var changePush = true
    @State private var resultPush = true

    var body: some View {
        Form {
            Section("Backend") {
                LabeledContent("Mac mini") {
                    Label(
                        store.isLive ? "Подключено" : "Не подключено",
                        systemImage: store.isLive ? "checkmark.circle.fill" : "exclamationmark.circle"
                    )
                    .foregroundStyle(store.isLive ? .green : .orange)
                }

                TextField("Адрес", text: $baseURL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()

                TextField("Логин", text: $username)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()

                SecureField("Пароль", text: $password)

                LabeledContent("Канал") {
                    Text("Tailscale HTTPS")
                }

                LabeledContent("API") {
                    Text(store.connectionLabel)
                        .foregroundStyle(.secondary)
                }

                if let error = store.lastError {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                }

                Button("Сохранить и проверить") {
                    Task {
                        await store.configureConnection(
                            baseURL: baseURL,
                            username: username,
                            password: password
                        )
                        if store.isLive {
                            password = ""
                        }
                    }
                }

                Button("Обновить") {
                    Task {
                        await store.refresh()
                    }
                }

                Button("Сбросить подключение", role: .destructive) {
                    store.disconnect()
                    baseURL = BackendCredentialStore.defaultBaseURLString
                    username = ""
                    password = ""
                }
            }

            Section("Уведомления") {
                Toggle("Новые отчёты", isOn: $reportPush)
                Toggle("Изменения закупок", isOn: $changePush)
                Toggle("Результаты", isOn: $resultPush)
            }

            Section("Приложение") {
                LabeledContent("Версия", value: "0.3.0-dev")
                LabeledContent("Режим", value: store.isLive ? "Live" : "Mock fallback")
            }
        }
        .navigationTitle("Настройки")
    }
}
