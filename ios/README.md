# AI Fantasy GM — iOS

This folder contains the native SwiftUI client for AI Fantasy GM.

## Current milestone
- Native iPhone navigation and dashboard
- Sign in / sign up UI
- ESPN league connection form
- My Team roster with Fantasy OVR presentation
- Waivers, League, and AI GM screens
- API client isolated behind `APIClient`

## Backend transition
The iOS client intentionally keeps the API base URL configurable. The existing FastAPI service can be used during migration, then moved off Render without rewriting the app UI.

Open a new iOS App project in Xcode named **AIFantasyGM**, target iOS 17+, then add the Swift files in `ios/AIFantasyGM`.
