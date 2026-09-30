import Foundation

struct FantasyPlayer: Identifiable, Codable, Hashable {
    let id: String
    let name: String
    let position: String
    let proTeam: String
    let fantasyOVR: Int?
}

struct LeagueSummary: Codable {
    let leagueName: String
    let teamName: String
    let record: String?
}

struct ESPNConnection: Codable {
    var leagueID = ""
    var teamID = ""
    var season = String(Calendar.current.component(.year, from: Date()))
    var espnS2 = ""
    var swid = ""
}
