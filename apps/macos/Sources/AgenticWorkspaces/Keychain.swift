import Foundation
import Security

enum Keychain {
    private static let service = "dev.agentic-stack.workspaces"
    private static let queue = DispatchQueue(label: "dev.agentic-stack.credentials", qos: .userInitiated)

    private static func perform<T: Sendable>(_ operation: @escaping @Sendable () throws -> T) async throws -> T {
        try await withCheckedThrowingContinuation { continuation in
            queue.async {
                // Legacy macOS items can otherwise display an authentication prompt
                // during a background refresh. Serialize these process-local calls.
                var previous: DarwinBoolean = true
                SecKeychainGetUserInteractionAllowed(&previous)
                SecKeychainSetUserInteractionAllowed(false)
                defer { SecKeychainSetUserInteractionAllowed(previous.boolValue) }
                do { continuation.resume(returning: try operation()) }
                catch { continuation.resume(throwing: error) }
            }
        }
    }

    static func read(_ account: String) async throws -> String {
        try await perform { try readStored(account) }
    }

    static func save(_ value: String, account: String) async throws {
        try await perform { try saveStored(value, account: account) }
    }

    private static func readStored(_ account: String) throws -> String {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: account,
            kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if status == errSecItemNotFound { return "" }
        guard status == errSecSuccess, let data = result as? Data else {
            throw BridgeError(message: "The saved credential is unavailable from Keychain (\(status)). Re-enter it in Hosting or Settings, or use this Mac.")
        }
        return String(decoding: data, as: UTF8.self)
    }

    private static func saveStored(_ value: String, account: String) throws {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: account]
        if value.isEmpty {
            let status = SecItemDelete(query as CFDictionary)
            guard status == errSecSuccess || status == errSecItemNotFound else {
                throw BridgeError(message: "Keychain could not remove the credential (\(status)).")
            }
            return
        }
        let data = Data(value.utf8)
        var status = SecItemUpdate(query as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if status == errSecItemNotFound {
            var item = query
            item[kSecValueData as String] = data
            item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            status = SecItemAdd(item as CFDictionary, nil)
        }
        guard status == errSecSuccess else {
            throw BridgeError(message: "Keychain could not save the credential (\(status)).")
        }
    }
}
