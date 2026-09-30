import Foundation

actor APIClient {
    static let shared = APIClient()
    // Temporary bridge while the backend is migrated. The native UI no longer depends on the website.
    private let baseURL = URL(string: "https://ai-fantasy-gm.onrender.com")!

    func request<T: Decodable>(_ path: String, method: String = "GET", token: String? = nil, body: Data? = nil) async throws -> T {
        guard let url = URL(string: path, relativeTo: baseURL) else { throw APIError.invalidResponse }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = body
        request.timeoutInterval = 45
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            let detail = (try? JSONDecoder().decode(ErrorEnvelope.self, from: data))?.detail
            if http.statusCode == 401 { throw APIError.sessionExpired }
            throw APIError.message(detail ?? "Server error \(http.statusCode).")
        }
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw APIError.message("The app could not read the server response.") }
    }

    func login(email: String, password: String) async throws -> AuthResponse {
        let body = try JSONEncoder().encode(AuthRequest(email: email, password: password, name: "Fantasy Manager"))
        return try await request("/auth/login", method: "POST", body: body)
    }
    func signup(name: String, email: String, password: String) async throws -> AuthResponse {
        let body = try JSONEncoder().encode(AuthRequest(email: email, password: password, name: name))
        return try await request("/auth/signup", method: "POST", body: body)
    }
    func connectESPN(_ connection: ESPNConnection, token: String) async throws -> ESPNConnectResponse {
        try await request("/espn/connect", method: "POST", token: token, body: connection.requestBody())
    }
    func dashboard(token: String) async throws -> DashboardResponse { try await request("/dashboard", token: token) }
    func fantasyOVR(token: String) async throws -> FantasyOVRResponse { try await request("/api/fantasy-ovr", token: token) }
    func waivers(token: String) async throws -> WaiversResponse { try await request("/espn/waivers", token: token) }
    func askGM(_ question: String, token: String) async throws -> GMResponse {
        try await request("/ai/gm", method: "POST", token: token, body: JSONEncoder().encode(GMRequest(question: question)))
    }
}

private struct ErrorEnvelope: Codable { let detail: String? }

enum APIError: LocalizedError {
    case invalidResponse, invalidInput, sessionExpired, message(String)
    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "The server returned an invalid response."
        case .invalidInput: return "Check the League ID, Team ID, and season."
        case .sessionExpired: return "Your session expired. Please sign in again."
        case .message(let text): return text
        }
    }
}
