import Foundation
import Security

@MainActor
final class SessionStore: ObservableObject {
    @Published var isSignedIn = false
    @Published var leagueConnected = false
    @Published var players: [FantasyPlayer] = []
    @Published var league: LeagueSummary?

    private(set) var token: String?

    init() {
        token = KeychainToken.load()
        isSignedIn = token != nil
    }

    func setToken(_ value: String) {
        token = value
        KeychainToken.save(value)
        isSignedIn = true
    }

    func signOut() {
        token = nil
        KeychainToken.delete()
        isSignedIn = false
        leagueConnected = false
        players = []
    }
}

enum KeychainToken {
    private static let service = "AIFantasyGM"
    private static let account = "auth-token"

    static func save(_ token: String) {
        delete()
        let data = Data(token.utf8)
        SecItemAdd([
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecValueData: data
        ] as CFDictionary, nil)
    }

    static func load() -> String? {
        var result: CFTypeRef?
        let status = SecItemCopyMatching([
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecReturnData: true,
            kSecMatchLimit: kSecMatchLimitOne
        ] as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete() {
        SecItemDelete([
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account
        ] as CFDictionary)
    }
}
