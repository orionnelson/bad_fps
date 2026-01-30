FPS Authoritative Multiplayer (Python + Three.js)

One codebase, two clean apps:
- `server/`: authoritative simulation + WS/HTTP API (Python)
- `client/`: thin renderer/input/UI (Three.js)

Quickstart (local)

1) Start the server:
   `python -m pip install -r server/requirements.txt`
   `python -m server.app` # Backend

2) Prepare client shared files (optional but recommended):
   python tools/pack_assets.py

3) Serve the client separately: 
   `cd client`
   `python -m http.server 5173` # Frontend 

4) Open the game:
   http://localhost:5173/public/index.html

Online multiplayer
- Host `client/` on any static host.
- Run `server/` on a VPS/container.
- Point the client to `wss://YOUR_SERVER/ws`.


Local multiplayer
- Toggle "Local Split" in the client UI.
- The client opens 2 WS connections to the same server (localhost or remote).
<img width="2517" height="1238" alt="image" src="https://github.com/user-attachments/assets/a8977fe4-7f65-4f2d-a1f9-54653467a8de" />
- Single player 
<img width="3028" height="1462" alt="image" src="https://github.com/user-attachments/assets/24d3af4f-544a-40b1-bbee-7d34db552911" />
- Online Multiplayer 

<img width="2473" height="1288" alt="image" src="https://github.com/user-attachments/assets/055dc40b-babc-43a7-bd80-222d7f1faccd" />
- Local Multiplayer
