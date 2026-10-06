import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: AppStore
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
                LabeledContent("Канал") {
                    Text("Tailscale / local dev")
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

                Button("Обновить") {
                    Task {
                        await store.refresh()
                    }
                }
            }

            Section("Уведомления") {
                Toggle("Новые отчёты", isOn: $reportPush)
                Toggle("Изменения закупок", isOn: $changePush)
                Toggle("Результаты", isOn: $resultPush)
            }

            Section("Приложение") {
                LabeledContent("Версия", value: "0.2.0-dev")
                LabeledContent("Режим", value: store.isLive ? "Live" : "Mock fallback")
            }
        }
        .navigationTitle("Настройки")
    }
}
