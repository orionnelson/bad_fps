FPS Authoritative Multiplayer (Python + Three.js)

One codebase, two clean apps:
- `server/`: authoritative simulation + WS/HTTP API (Python)
- `client/`: thin renderer/input/UI (Three.js)

Quickstart (local)

1) Start the server:
   python -m pip install -r server/requirements.txt
   python -m server.app

2) Prepare client shared files (optional but recommended):
   python tools/pack_assets.py

3) Serve the client separately:
   python -m server.app # Backend
   cd client
   python -m http.server 5173 # Frontend 

4) Open the game:
   http://localhost:5173/public/index.html

Online multiplayer
- Host `client/` on any static host.
- Run `server/` on a VPS/container.
- Point the client to `wss://YOUR_SERVER/ws`.


Local multiplayer
- Toggle "Local Split" in the client UI.
- The client opens 2 WS connections to the same server (localhost or remote).
