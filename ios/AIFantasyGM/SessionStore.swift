import Foundation
import Security

@MainActor
final class SessionStore: ObservableObject {
    @Published var isSignedIn=false, leagueConnected=false, isLoading=false
    @Published var players:[FantasyPlayer]=[]
    @Published var leagueName="", teamName="", recordText=""
    @Published var rank:Int?
    @Published var errorMessage:String?
    private(set) var token:String?

    init(){ token=KeychainToken.load(); isSignedIn=token != nil; if isSignedIn { Task { await refresh() } } }

    func authenticate(email:String,password:String,signup:Bool=false,name:String="Fantasy Manager") async {
        isLoading=true; errorMessage=nil
        do {
            let r = try await (signup ? APIClient.shared.signup(name:name,email:email,password:password) : APIClient.shared.login(email:email,password:password))
            setToken(r.token); await refresh()
        } catch { errorMessage=error.localizedDescription }
        isLoading=false
    }
    func connect(_ c:ESPNConnection) async -> Bool {
        guard let token else{return false}; isLoading=true; errorMessage=nil
        do { let r=try await APIClient.shared.connectESPN(c,token:token); leagueConnected=r.connected;leagueName=r.name;rank=r.rank;await refresh();isLoading=false;return true }
        catch { errorMessage=error.localizedDescription;isLoading=false;return false }
    }
    func refresh() async {
        guard let token else{return}; isLoading=true
        do {
            async let d=APIClient.shared.dashboard(token:token); async let o=APIClient.shared.fantasyOVR(token:token)
            let (dash,ovr)=try await(d,o); leagueConnected=true;leagueName=dash.league;teamName=dash.team.name;rank=dash.rank
            if let r=dash.record { recordText="\(r.wins ?? 0)-\(r.losses ?? 0)" + ((r.ties ?? 0)>0 ? "-\(r.ties ?? 0)":"") }
            let ratings=Dictionary(uniqueKeysWithValues:ovr.players.map{($0.id,$0.fantasyOVR)})
            players=dash.team.roster.map{ p in var x=p;x.fantasyOVR=ratings[p.id] ?? p.fantasyOVR;return x }
        } catch APIError.sessionExpired { signOut();errorMessage="Your session expired. Please sign in again." }
        catch { leagueConnected=false }
        isLoading=false
    }
    func setToken(_ v:String){token=v;KeychainToken.save(v);isSignedIn=true}
    func signOut(){token=nil;KeychainToken.delete();isSignedIn=false;leagueConnected=false;players=[]}
}
enum KeychainToken {
    static let service="AIFantasyGM",account="auth-token"
    static func save(_ t:String){delete();SecItemAdd([kSecClass:kSecClassGenericPassword,kSecAttrService:service,kSecAttrAccount:account,kSecValueData:Data(t.utf8)] as CFDictionary,nil)}
    static func load()->String?{var r:CFTypeRef?;let s=SecItemCopyMatching([kSecClass:kSecClassGenericPassword,kSecAttrService:service,kSecAttrAccount:account,kSecReturnData:true,kSecMatchLimit:kSecMatchLimitOne] as CFDictionary,&r);guard s==errSecSuccess,let d=r as? Data else{return nil};return String(data:d,encoding:.utf8)}
    static func delete(){SecItemDelete([kSecClass:kSecClassGenericPassword,kSecAttrService:service,kSecAttrAccount:account] as CFDictionary)}
}
