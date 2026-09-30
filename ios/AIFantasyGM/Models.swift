import Foundation

struct UserEnvelope: Codable { let user: AppUser }
struct AppUser: Codable { let id: Int; let email: String; let name: String }
struct AuthResponse: Codable { let token: String; let user: AppUser }
struct AuthRequest: Codable { let email: String; let password: String; let name: String }

struct ESPNConnection: Codable {
    var leagueID = ""
    var teamID = ""
    var season = String(Calendar.current.component(.year, from: Date()))
    var espnS2 = ""
    var swid = ""

    enum CodingKeys: String, CodingKey {
        case leagueID = "league_id", teamID = "team_id", season, espnS2 = "espn_s2", swid
    }

    func requestBody() throws -> Data {
        struct Payload: Codable {
            let league_id: String; let team_id: Int; let season: Int
            let espn_s2: String; let swid: String
        }
        guard let team = Int(teamID), let year = Int(season) else { throw APIError.invalidInput }
        return try JSONEncoder().encode(Payload(league_id: leagueID, team_id: team, season: year, espn_s2: espnS2, swid: swid))
    }
}

struct ESPNConnectResponse: Codable { let connected: Bool; let name: String; let teams: Int; let rank: Int? }

struct DashboardResponse: Codable {
    let league: String
    let rank: Int?
    let record: Record?
    let team: Team
    let scoringPeriod: Int?
    enum CodingKeys: String, CodingKey { case league, rank, record, team; case scoringPeriod = "scoring_period" }
}
struct Record: Codable { let wins: Int?; let losses: Int?; let ties: Int? }
struct Team: Codable { let id: Int?; let name: String; let roster: [FantasyPlayer] }
struct FantasyPlayer: Identifiable, Codable, Hashable {
    let id: Int
    let name: String
    let position: String
    let proTeamID: Int?
    let injuryStatus: String?
    let lineupSlot: String?
    let totalPoints: Double?
    var fantasyOVR: Int?

    enum CodingKeys: String, CodingKey {
        case id, name, position
        case proTeamID = "pro_team_id", injuryStatus = "injury_status", lineupSlot = "lineup_slot"
        case totalPoints = "total_points", fantasyOVR = "fantasy_ovr"
    }
}
struct FantasyOVRResponse: Codable { let players: [FantasyPlayer] }
struct WaiversResponse: Codable { let players: [FantasyPlayer]; let count: Int }
struct GMRequest: Codable { let question: String }
struct GMResponse: Codable { let answer: String }
