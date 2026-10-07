import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: AppStore

    @State private var baseURL = BackendCredentialStore.savedBaseURL
    @State private var pairingCode = ""

    private var appVersion: String {
        let version =
            Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString")
            as? String
        return version ?? "0.7.0"
    }

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
                    Task {
                        await store.disconnect()
                        baseURL = BackendCredentialStore.defaultBaseURLString
                        pairingCode = ""
                    }
                }
            }

            Section("Уведомления") {
                LabeledContent("APNs", value: store.pushStatusLabel)

                if let error = store.pushRegistrationError {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                }

                Button("Включить уведомления") {
                    Task {
                        await store.requestPushNotifications()
                    }
                }

                Text(
                    "Уведомления открывают только отчёт или карточку закупки. "
                        + "Push не принимает решение и не выполняет действие на ЭТП."
                )
                .font(.caption)
                .foregroundStyle(.secondary)
            }

            Section("Приложение") {
                LabeledContent("Версия", value: "\(appVersion)-dev")
                LabeledContent(
                    "Режим",
                    value: store.isLive ? "Live" : "Demo / offline"
                )
                Text(
                    "MOB-3: live-отчёты, человеческие GO / NO GO / DEFER, "
                        + "APNs-регистрация и безопасные deep links. "
                        + "Подписание, оплата и отправка заявки остаются вне мобильного контура."
                )
                .font(.caption)
                .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("Настройки")
    }
}
