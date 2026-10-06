import Foundation
import Security
import UIKit

enum BackendCredentialStore {
    static let defaultBaseURLString = "https://mac-mini-master.tail786c4b.ts.net:9443"

    private static let baseURLKey = "tenderAgent.backend.baseURL"
    private static let deviceIDKey = "tenderAgent.backend.deviceID"
    private static let keychainService = "com.arvectum.tenderagent.backend"
    private static let keychainAccount = "mobile-bearer-token"

    static var savedBaseURL: String {
        UserDefaults.standard.string(forKey: baseURLKey) ?? defaultBaseURLString
    }

    static var deviceID: String {
        if let existing = UserDefaults.standard.string(forKey: deviceIDKey),
           !existing.isEmpty {
            return existing
        }
        let generated = UUID().uuidString.lowercased()
        UserDefaults.standard.set(generated, forKey: deviceIDKey)
        return generated
    }

    static var deviceName: String {
        UIDevice.current.name
    }

    static func loadConfiguration() -> TenderAgentAPIConfiguration? {
        guard
            let baseURL = URL(string: savedBaseURL),
            let token = loadToken(),
            !token.isEmpty
        else {
            return nil
        }
        return TenderAgentAPIConfiguration(
            baseURL: baseURL,
            accessToken: token
        )
    }

    @discardableResult
    static func savePairing(
        baseURLString: String,
        accessToken: String
    ) throws -> TenderAgentAPIConfiguration {
        guard
            let baseURL = URL(
                string: baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
            )
        else {
            throw CredentialStoreError.invalidURL
        }
        guard !accessToken.isEmpty else {
            throw CredentialStoreError.missingToken
        }

        UserDefaults.standard.set(baseURL.absoluteString, forKey: baseURLKey)
        try saveToken(accessToken)

        return TenderAgentAPIConfiguration(
            baseURL: baseURL,
            accessToken: accessToken
        )
    }

    static func clear() {
        UserDefaults.standard.removeObject(forKey: baseURLKey)
        SecItemDelete(keychainQuery() as CFDictionary)
    }

    private static func saveToken(_ token: String) throws {
        SecItemDelete(keychainQuery() as CFDictionary)

        var query = keychainQuery()
        query[kSecValueData as String] = Data(token.utf8)
        query[kSecAttrAccessible as String] =
            kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly

        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw CredentialStoreError.keychain(status)
        }
    }

    private static func loadToken() -> String? {
        var query = keychainQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }

    private static func keychainQuery() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount
        ]
    }
}

enum CredentialStoreError: LocalizedError {
    case invalidURL
    case missingToken
    case keychain(OSStatus)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Некорректный адрес backend."
        case .missingToken:
            return "Backend не вернул токен."
        case let .keychain(status):
            return "Не удалось сохранить токен в Keychain (\(status))."
        }
    }
}
