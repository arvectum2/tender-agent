import Foundation
import Security

enum BackendCredentialStore {
    static let defaultBaseURLString = "https://mac-mini-master.tail786c4b.ts.net:9443"

    private static let baseURLKey = "tenderAgent.backend.baseURL"
    private static let usernameKey = "tenderAgent.backend.username"
    private static let keychainService = "com.arvectum.tenderagent.backend"
    private static let keychainAccount = "basic-auth-password"

    static var savedBaseURL: String {
        UserDefaults.standard.string(forKey: baseURLKey) ?? defaultBaseURLString
    }

    static var savedUsername: String {
        UserDefaults.standard.string(forKey: usernameKey) ?? ""
    }

    static func loadConfiguration() -> TenderAgentAPIConfiguration? {
        let base = savedBaseURL
        let username = savedUsername
        guard
            let baseURL = URL(string: base),
            !username.isEmpty,
            let password = loadPassword(),
            !password.isEmpty
        else {
            return nil
        }
        return TenderAgentAPIConfiguration(
            baseURL: baseURL,
            username: username,
            password: password
        )
    }

    @discardableResult
    static func save(
        baseURLString: String,
        username: String,
        password: String
    ) throws -> TenderAgentAPIConfiguration {
        guard let baseURL = URL(string: baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)) else {
            throw CredentialStoreError.invalidURL
        }
        let cleanUsername = username.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanUsername.isEmpty else {
            throw CredentialStoreError.missingUsername
        }

        let effectivePassword: String
        if password.isEmpty, let existing = loadPassword(), !existing.isEmpty {
            effectivePassword = existing
        } else {
            effectivePassword = password
        }
        guard !effectivePassword.isEmpty else {
            throw CredentialStoreError.missingPassword
        }

        UserDefaults.standard.set(baseURL.absoluteString, forKey: baseURLKey)
        UserDefaults.standard.set(cleanUsername, forKey: usernameKey)
        try savePassword(effectivePassword)

        return TenderAgentAPIConfiguration(
            baseURL: baseURL,
            username: cleanUsername,
            password: effectivePassword
        )
    }

    static func clear() {
        UserDefaults.standard.removeObject(forKey: baseURLKey)
        UserDefaults.standard.removeObject(forKey: usernameKey)
        SecItemDelete(keychainQuery() as CFDictionary)
    }

    private static func savePassword(_ password: String) throws {
        SecItemDelete(keychainQuery() as CFDictionary)

        var query = keychainQuery()
        query[kSecValueData as String] = Data(password.utf8)
        query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly

        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw CredentialStoreError.keychain(status)
        }
    }

    private static func loadPassword() -> String? {
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
    case missingUsername
    case missingPassword
    case keychain(OSStatus)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Некорректный адрес backend."
        case .missingUsername:
            return "Введите логин."
        case .missingPassword:
            return "Введите пароль."
        case let .keychain(status):
            return "Не удалось сохранить пароль в Keychain (\(status))."
        }
    }
}
