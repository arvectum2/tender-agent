import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: AppStore

    @State private var baseURL = BackendCredentialStore.savedBaseURL
    @State private var pairingCode = ""

    @State private var reportPush = true
    @State private var changePush = true
    @State private var resultPush = true

    var body: some View {
        Form {
            Section("Backend") {
                LabeledContent("Mac mini") {
                    Label(
                        store.isLive ? "Подключено" : "Не подключено",
                        systemImage: store.isLive
                            ? "checkmark.circle.fill"
                            : "exclamationmark.circle"
                    )
                    .foregroundStyle(store.isLive ? .green : .orange)
                }

                TextField("Адрес", text: $baseURL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()

                TextField("6-значный код", text: $pairingCode)
                    .keyboardType(.numberPad)

                LabeledContent("Устройство") {
                    Text(BackendCredentialStore.deviceName)
                        .lineLimit(1)
                }

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

                Button("Подключить по коду") {
                    Task {
                        await store.pair(
                            baseURL: baseURL,
                            pairingCode: pairingCode
                        )
                        if store.isLive {
                            pairingCode = ""
                        }
                    }
                }
                .disabled(pairingCode.count != 6)

                Button("Обновить") {
                    Task {
                        await store.refresh()
                    }
                }
                .disabled(!store.isLive)

                Button("Сбросить подключение", role: .destructive) {
                    store.disconnect()
                    baseURL = BackendCredentialStore.defaultBaseURLString
                    pairingCode = ""
                }
            }

            Section("Уведомления") {
                Toggle("Новые отчёты", isOn: $reportPush)
                Toggle("Изменения закупок", isOn: $changePush)
                Toggle("Результаты", isOn: $resultPush)
            }

            Section("Приложение") {
                LabeledContent("Версия", value: "0.4.0-dev")
                LabeledContent(
                    "Режим",
                    value: store.isLive ? "Live" : "Mock fallback"
                )
            }
        }
        .navigationTitle("Настройки")
    }
}
