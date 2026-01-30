Client (Three.js)

This folder is the thin web client. It is served separately from the Python server.

Dev quickstart (no bundler):
1) Copy shared files into client/public/shared (optional but recommended):
   python ../tools/pack_assets.py

2) Serve this `client/` directory as static files:
   python -m http.server 5173

3) Open:
   http://localhost:5173/public/index.html

In the UI:
- Server WS URL: ws://localhost:8765/ws
- Click Matchmake or Join
- Toggle Local Split to run 2 players from the same machine (two WS connections)
