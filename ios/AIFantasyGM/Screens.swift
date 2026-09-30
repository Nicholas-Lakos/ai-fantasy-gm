import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var session: SessionStore
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Front Office").font(.largeTitle.bold())
                    GroupBox("Your Team") {
                        HStack {
                            VStack(alignment: .leading) {
                                Text(session.league?.teamName ?? "Connect your ESPN team").font(.headline)
                                Text(session.league?.record ?? "Live fantasy analysis").foregroundStyle(.secondary)
                            }
                            Spacer()
                            Image(systemName: "chart.line.uptrend.xyaxis")
                        }
                    }
                    NavigationLink("Connect ESPN League") { ESPNConnectView() }
                        .buttonStyle(.borderedProminent)
                }.padding()
            }
        }
    }
}

struct MyTeamView: View {
    @EnvironmentObject var session: SessionStore
    var body: some View {
        NavigationStack {
            List(session.players) { player in
                HStack(spacing: 14) {
                    ZStack {
                        Circle().fill(.thinMaterial).frame(width: 52, height: 52)
                        Text(player.fantasyOVR.map(String.init) ?? "—").font(.headline.bold())
                    }
                    VStack(alignment: .leading) {
                        Text(player.name).font(.headline)
                        Text("\(player.position) · \(player.proTeam)").foregroundStyle(.secondary)
                        if let ovr = player.fantasyOVR { Text("Fantasy OVR \(ovr) · ESPN stats").font(.caption) }
                    }
                }
            }
            .navigationTitle("My Team")
            .overlay {
                if session.players.isEmpty {
                    ContentUnavailableView("No roster loaded", systemImage: "person.3", description: Text("Connect your ESPN league to import your roster."))
                }
            }
        }
    }
}

struct ESPNConnectView: View {
    @State private var connection = ESPNConnection()
    var body: some View {
        Form {
            Section("League") {
                TextField("League ID", text: $connection.leagueID).keyboardType(.numberPad)
                TextField("Team ID", text: $connection.teamID).keyboardType(.numberPad)
                TextField("Season", text: $connection.season).keyboardType(.numberPad)
            }
            Section("Private league credentials") {
                SecureField("espn_s2", text: $connection.espnS2)
                SecureField("SWID", text: $connection.swid)
            }
            Section {
                Button("Test & Import") {
                    // Connect to /espn/connect after backend migration is finalized.
                }
            }
        }.navigationTitle("Connect ESPN")
    }
}

struct WaiversView: View {
    var body: some View { NavigationStack { ContentUnavailableView("Waiver Wire", systemImage: "magnifyingglass", description: Text("ESPN waiver recommendations will appear here.")).navigationTitle("Waivers") } }
}

struct AIGMView: View {
    @State private var prompt = ""
    var body: some View {
        NavigationStack {
            VStack {
                Spacer()
                ContentUnavailableView("AI General Manager", systemImage: "sparkles", description: Text("Ask about trades, starts, drops, and waiver targets."))
                Spacer()
                HStack {
                    TextField("Ask your GM…", text: $prompt).textFieldStyle(.roundedBorder)
                    Button { } label: { Image(systemName: "arrow.up.circle.fill").font(.title) }
                }.padding()
            }.navigationTitle("AI GM")
        }
    }
}

struct SettingsView: View {
    @EnvironmentObject var session: SessionStore
    var body: some View {
        NavigationStack {
            Form {
                Section("Account") { Button("Sign Out", role: .destructive) { session.signOut() } }
                Section("About") { LabeledContent("App", value: "AI Fantasy GM"); LabeledContent("Client", value: "Native iOS / SwiftUI") }
            }.navigationTitle("Settings")
        }
    }
}
