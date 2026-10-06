import Foundation
import UIKit
@preconcurrency import UserNotifications

extension Notification.Name {
    static let tenderAgentAPNSToken = Notification.Name("TenderAgentAPNSToken")
    static let tenderAgentPushRegistrationFailure = Notification.Name(
        "TenderAgentPushRegistrationFailure"
    )
    static let tenderAgentDeepLink = Notification.Name("TenderAgentDeepLink")
}

enum TenderAgentDeepLink: Equatable, Sendable {
    case procurement(String)
    case digest

    init?(url: URL) {
        guard url.scheme?.lowercased() == "tenderagent" else {
            return nil
        }

        switch url.host?.lowercased() {
        case "procurement":
            guard
                let dealID = url.pathComponents.dropFirst().first?
                    .removingPercentEncoding?
                    .trimmingCharacters(in: .whitespacesAndNewlines),
                !dealID.isEmpty
            else {
                return nil
            }
            self = .procurement(dealID)
        case "digest":
            self = .digest
        default:
            return nil
        }
    }

    init?(userInfo: [AnyHashable: Any]) {
        if
            let rawDeepLink = userInfo["deep_link"] as? String,
            let url = URL(string: rawDeepLink),
            let parsed = TenderAgentDeepLink(url: url)
        {
            self = parsed
            return
        }

        if
            let dealID = userInfo["deal_id"] as? String,
            !dealID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        {
            self = .procurement(dealID)
            return
        }

        return nil
    }

    var url: URL {
        switch self {
        case let .procurement(dealID):
            var components = URLComponents()
            components.scheme = "tenderagent"
            components.host = "procurement"
            components.path = "/\(dealID)"
            return components.url!
        case .digest:
            return URL(string: "tenderagent://digest")!
        }
    }
}

@MainActor
enum PushNotificationRegistrar {
    static func requestAuthorization() async -> UNAuthorizationStatus {
        let center = UNUserNotificationCenter.current()
        do {
            _ = try await center.requestAuthorization(options: [.alert, .badge, .sound])
        } catch {
            NotificationCenter.default.post(
                name: .tenderAgentPushRegistrationFailure,
                object: error.localizedDescription
            )
        }
        return await registerIfAuthorized()
    }

    static func registerIfAuthorized() async -> UNAuthorizationStatus {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        switch settings.authorizationStatus {
        case .authorized, .provisional, .ephemeral:
            UIApplication.shared.registerForRemoteNotifications()
        case .notDetermined, .denied:
            break
        @unknown default:
            break
        }
        return settings.authorizationStatus
    }

    static func statusLabel(_ status: UNAuthorizationStatus) -> String {
        switch status {
        case .notDetermined:
            "Не запрошены"
        case .denied:
            "Запрещены в iOS"
        case .authorized:
            "Разрешены — регистрация APNs"
        case .provisional:
            "Разрешены предварительно"
        case .ephemeral:
            "Разрешены временно"
        @unknown default:
            "Неизвестный статус"
        }
    }
}

@MainActor
final class TenderAgentAppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        NotificationCenter.default.post(
            name: .tenderAgentAPNSToken,
            object: token
        )
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        NotificationCenter.default.post(
            name: .tenderAgentPushRegistrationFailure,
            object: error.localizedDescription
        )
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (
            UNNotificationPresentationOptions
        ) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        if let deepLink = TenderAgentDeepLink(
            userInfo: response.notification.request.content.userInfo
        ) {
            NotificationCenter.default.post(
                name: .tenderAgentDeepLink,
                object: deepLink.url
            )
        }
        completionHandler()
    }
}
