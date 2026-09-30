import Foundation

actor APIClient {
    static let shared = APIClient()

    // Change this once the FastAPI service is moved off Render.
    private let baseURL = URL(string: "https://ai-fantasy-gm.onrender.com")!

    func request<T: Decodable>(_ path: String, method: String = "GET", token: String? = nil, body: Data? = nil) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = method
        request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            if http.statusCode == 401 { throw APIError.sessionExpired }
            throw APIError.server(http.statusCode)
        }
        return try JSONDecoder().decode(T.self, from: data)
    }
}

enum APIError: LocalizedError {
    case invalidResponse, sessionExpired, server(Int)
    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "The server returned an invalid response."
        case .sessionExpired: return "Your session expired. Please sign in again."
        case .server(let code): return "Server error \(code)."
        }
    }
}
