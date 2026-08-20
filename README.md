# AI Fantasy GM

AI Fantasy GM is a browser-based ESPN Fantasy Baseball command center with account authentication, ESPN league import, standings/team views, and league-aware GM decision support.

## Deployment

This project is configured for Render using the included `render.yaml` and Dockerfile.

## Structure

- `frontend/` — responsive Safari/Chrome web UI
- `backend/` — FastAPI API, authentication, ESPN integration, and AI GM endpoint
- `render.yaml` — Render web-service configuration
- `Dockerfile` — production container
