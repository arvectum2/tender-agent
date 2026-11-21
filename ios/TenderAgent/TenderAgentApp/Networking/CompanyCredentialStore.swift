import Foundation
import Security

/// All company credentials (including their HTTPS origin) stay in a separate Keychain item.
enum CompanyCredentialStore {
    private static var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: "com.arvectum.tenderagent.company",
         kSecAttrAccount as String: "company-connections-v1"]
    }

    static func load() throws -> [CompanyConnection] {
        var request = query
        request[kSecReturnData as String] = true
        request[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(request as CFDictionary, &result)
        if status == errSecItemNotFound { return [] }
        guard status == errSecSuccess, let data = result as? Data else { throw CompanyConnectionError.storage }
        return try JSONDecoder().decode([CompanyConnection].self, from: data)
    }

    static func save(_ connections: [CompanyConnection]) throws {
        let data = try JSONEncoder().encode(connections)
        let update = [kSecValueData as String: data]
        let status = SecItemUpdate(query as CFDictionary, update as CFDictionary)
        if status == errSecItemNotFound {
            var item = query
            item[kSecValueData as String] = data
            item[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            guard SecItemAdd(item as CFDictionary, nil) == errSecSuccess else { throw CompanyConnectionError.storage }
        } else if status != errSecSuccess {
            throw CompanyConnectionError.storage
        }
    }
}
