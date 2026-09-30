import SwiftUI

struct RootView: View {
    @EnvironmentObject var session: SessionStore

    var body: some View {
        if session.isSignedIn {
            MainTabView()
        } else {
            SignInView()
        }
    }
}

struct SignInView: View {
    @EnvironmentObject var session: SessionStore
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 18) {
                Spacer()
                Image(systemName: "baseball.fill").font(.system(size: 64))
                Text("AI Fantasy GM").font(.largeTitle.bold())
                Text("Your fantasy baseball front office").foregroundStyle(.secondary)
                TextField("Email", text: $email).textInputAutocapitalization(.never).keyboardType(.emailAddress).textFieldStyle(.roundedBorder)
                SecureField("Password", text: $password).textFieldStyle(.roundedBorder)
                Button("Sign In") {
                    // Auth wiring is the next backend-migration step.
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                Spacer()
            }
            .padding()
        }
    }
}

struct MainTabView: View {
    var body: some View {
        TabView {
            DashboardView().tabItem { Label("Home", systemImage: "house.fill") }
            MyTeamView().tabItem { Label("My Team", systemImage: "person.3.fill") }
            WaiversView().tabItem { Label("Waivers", systemImage: "magnifyingglass") }
            AIGMView().tabItem { Label("AI GM", systemImage: "sparkles") }
            SettingsView().tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
    }
}
