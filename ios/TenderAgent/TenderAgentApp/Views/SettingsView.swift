import SwiftUI

struct SettingsView: View {
    @State private var reportPush = true
    @State private var changePush = true
    @State private var resultPush = true

    var body: some View {
        Form {
            Section("Backend") {
                LabeledContent("Mac mini") {
                    Label("Подключено", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                }
                LabeledContent("Канал") {
                    Text("Tailscale")
                }
                LabeledContent("API") {
                    Text("Mock")
                        .foregroundStyle(.secondary)
                }
            }

            Section("Уведомления") {
                Toggle("Новые отчёты", isOn: $reportPush)
                Toggle("Изменения закупок", isOn: $changePush)
                Toggle("Результаты", isOn: $resultPush)
            }

            Section("Приложение") {
                LabeledContent("Версия", value: "0.1.0-dev")
                LabeledContent("Режим", value: "Mock data")
            }
        }
        .navigationTitle("Настройки")
    }
}
