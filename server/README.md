Server (Python)

This is the authoritative game server:
- Validates inputs
- Runs simulation at 60 Hz
- Broadcasts snapshots at 15 Hz
- Manages rooms
- Basic anti-cheat baseline (rate limits + turn/seq checks)
- Optional SQLite persistence for leaderboard

Run:
1) Install dependencies:
   python -m pip install -r server/requirements.txt

2) Start server:
   python -m server.app

HTTP endpoints:
- GET  /health
- GET  /version
- GET  /rooms
- POST /matchmake
- GET  /leaderboard
- GET  /schema

WebSocket:
- ws://HOST:PORT/ws

Env vars:
- FPS_HOST
- FPS_PORT
- FPS_CORS_ALLOW_ALL (true/false)
- FPS_CORS_ORIGINS (comma-separated)
