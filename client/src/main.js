import { Renderer } from "./engine/renderer.js";
import { HUD } from "./game/hud.js";
import { createInput } from "./game/input.js";
import { makeSession } from "./net/transport.js";
import { ClientClock } from "./net/clock.js";
import { Entities } from "./game/entities.js";

const el = {
  overlay: document.getElementById("overlay"),
  viewport: document.getElementById("viewport"),
  status: document.getElementById("status"),
  wsUrl: document.getElementById("wsUrl"),
  name: document.getElementById("name"),
  room: document.getElementById("room"),
  split: document.getElementById("split"),
  btnMatchmake: document.getElementById("btnMatchmake"),
  btnJoin: document.getElementById("btnJoin"),
  invertX: document.getElementById("invertX"),
  invertY: document.getElementById("invertY"),
  sens: document.getElementById("sens"),
  sensVal: document.getElementById("sensVal"),
};

if (el.viewport) {
  el.viewport.tabIndex = 0;
  el.viewport.setAttribute("role", "application");
}

const SETTINGS_KEY = "fps_settings_rewrite_v1";

const settings = loadSettings();
bindSettingsUI(settings);

// If the client is opened from another device on the LAN, `localhost` points to
// that device, not the host running the server. Default to the current host.
try {
  const host = window.location.hostname;
  if (el.wsUrl && host && host !== "localhost" && host !== "127.0.0.1") {
    const v = (el.wsUrl.value || "").trim();
    if (v.includes("ws://localhost:") || v.includes("ws://127.0.0.1:")) {
      el.wsUrl.value = `ws://${host}:8765/ws`;
    }
  }
} catch {
  // ignore
}

const isMobile = ("ontouchstart" in window) || (navigator.maxTouchPoints || 0) > 0;
document.body.classList.toggle("mobile", isMobile);

const hud = new HUD();
const renderer = new Renderer(el.viewport);
const entities = new Entities(renderer.scene);

let sessions = [];
let running = false;

const SEND_HZ = 60;
const SEND_DT = 1 / SEND_HZ;

function setStatus(text) {
  el.status.textContent = text;
}

function showOverlay() {
  el.overlay.style.display = "grid";
}

function hideOverlay() {
  el.overlay.style.display = "none";
  try {
    el.viewport?.focus?.();
  } catch {
    // ignore
  }
}

function clamp(x, lo, hi) {
  return x < lo ? lo : x > hi ? hi : x;
}

function createPlayerSession(slot, wsUrl, name, mode) {
  const transport = makeSession({
    url: wsUrl,
    onStatus: (s) => setStatus(`P${slot + 1}: ${s}`),
  });
  const clock = new ClientClock(transport);
  const input = createInput({ mode, viewport: el.viewport, settings });

  const state = {
    slot,
    transport,
    clock,
    input,

    playerId: null,
    roomId: null,
    you: null,
    lastSeqAck: -1,

    seq: 0,
    sendAcc: 0,

    // Render smoothing based on authoritative pos/vel.
    renderPos: [0, 0, 0],
    renderVel: [0, 0, 0],
    hasState: false,

    // camera smoothing
    camPos: null,
  };

  transport.onOpen = () => {
    transport.send("hello", { clientVersion: "0.1.0" });
    // join is sent by connect() once we know the room.
  };

  transport.onMessage = (type, data) => {
    if (type === "error") {
      setStatus(`P${slot + 1}: error: ${data.message || "unknown"}`);
      return;
    }

    if (type === "welcome") {
      state.playerId = data.playerId;
      state.roomId = data.roomId;
      setStatus(`P${slot + 1}: joined ${data.roomId}`);
      if (slot === 0) hud.setRoom(data.roomId);
      return;
    }

    if (type === "pong") {
      clock.onPong(data);
      return;
    }

    if (type === "snapshot") {
      // We force wantDeltas=false in join, so snapshots should be full.
      const snap = data.mode ? data : data;
      if (!snap.you) return;
      state.you = snap.you;
      state.lastSeqAck = typeof snap.you.lastSeq === "number" ? snap.you.lastSeq : state.lastSeqAck;

      if (Array.isArray(snap.you.pos) && Array.isArray(snap.you.vel)) {
        state.renderPos = [snap.you.pos[0], snap.you.pos[1], snap.you.pos[2]];
        state.renderVel = [snap.you.vel[0], snap.you.vel[1], snap.you.vel[2]];
        state.hasState = true;
      }

      if (state.slot === 0) {
        hud.setVitals({ hp: snap.you.hp, armor: snap.you.armor, ammo: snap.you.ammo, weaponId: snap.you.weaponId });
        hud.setScore({ kills: snap.you.kills, deaths: snap.you.deaths });
      } else if (state.slot === 1) {
        hud.setVitalsP2({ hp: snap.you.hp, armor: snap.you.armor, ammo: snap.you.ammo, weaponId: snap.you.weaponId });
      }

      entities.applySnapshot(state.playerId, snap);
      return;
    }
  };

  return state;
}

async function connectSplit(wsUrl, baseName, matchmake, roomId) {
  // Always: join P1 first, then join P2 into the same room.
  const p1 = createPlayerSession(0, wsUrl, `${baseName}1`, "p1");
  sessions = [p1];
  await p1.transport.connect();

  p1.transport.send("join", {
    matchmake: !!matchmake,
    roomId: matchmake ? null : roomId,
    playerName: `${baseName}1`,
    wantDeltas: false,
  });

  await waitFor(() => !!p1.roomId, 3000);
  const joinRoom = p1.roomId;

  const p2 = createPlayerSession(1, wsUrl, `${baseName}2`, "p2");
  sessions.push(p2);
  await p2.transport.connect();

  p2.transport.send("join", {
    matchmake: false,
    roomId: joinRoom,
    playerName: `${baseName}2`,
    wantDeltas: false,
  });

  await waitFor(() => !!p2.roomId, 3000);

  document.body.classList.add("split");
  renderer.setSplitMode(true);
  entities.setLocalPlayers({ p1Id: p1.playerId, p2Id: p2.playerId });
}

async function connectSolo(wsUrl, name, matchmake, roomId) {
  const s = createPlayerSession(0, wsUrl, name, "solo");
  sessions = [s];
  await s.transport.connect();
  s.transport.send("join", {
    matchmake: !!matchmake,
    roomId: matchmake ? null : roomId,
    playerName: name,
    wantDeltas: false,
  });
  await waitFor(() => !!s.roomId, 3000);

  document.body.classList.remove("split");
  renderer.setSplitMode(false);
  entities.setLocalPlayers({ p1Id: s.playerId, p2Id: null });
}

async function connect({ matchmake }) {
  const wsUrl = el.wsUrl.value.trim();
  const baseName = (el.name.value.trim() || "Player").slice(0, 20);
  const roomId = el.room.value.trim() || null;
  const split = !!el.split.checked;

  if (isMobile && split) {
    setStatus("split-screen is disabled on mobile");
    showOverlay();
    running = false;
    return;
  }

  // close old
  for (const s of sessions) s.transport.close();
  sessions = [];
  running = false;

  try {
    if (split) {
      await connectSplit(wsUrl, baseName, matchmake, roomId);
    } else {
      await connectSolo(wsUrl, baseName, matchmake, roomId);
    }
    hideOverlay();
    running = true;
  } catch (e) {
    setStatus(`connect failed: ${e?.message || e}`);
    showOverlay();
    running = false;
  }
}

el.btnMatchmake.addEventListener("click", () => connect({ matchmake: true }));
el.btnJoin.addEventListener("click", () => connect({ matchmake: false }));

el.viewport.addEventListener("click", () => {
  // Pointer lock for player 1.
  sessions[0]?.input?.requestPointerLock?.();
});

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") showOverlay();
});

function integrate(state, dt) {
  if (!state.hasState) return;
  state.renderPos[0] += state.renderVel[0] * dt;
  state.renderPos[1] += state.renderVel[1] * dt;
  state.renderPos[2] += state.renderVel[2] * dt;
}

function setCameraFromState(state, look, dt) {
  const eye = 1.55;

  const pos = state.hasState ? [state.renderPos[0], state.renderPos[1] + eye, state.renderPos[2]] : [0, eye, 0];
  if (!state.camPos) {
    state.camPos = [...pos];
  } else {
    const k = 18.0;
    const a = 1.0 - Math.exp(-k * dt);
    state.camPos[0] += (pos[0] - state.camPos[0]) * a;
    state.camPos[1] += (pos[1] - state.camPos[1]) * a;
    state.camPos[2] += (pos[2] - state.camPos[2]) * a;
  }

  renderer.setCameraPose(state.slot, { pos: state.camPos, yaw: look.yaw, pitch: look.pitch });
}

function sendInputs(state, look, dt) {
  state.clock.tick(performance.now());
  state.sendAcc += dt;
  while (state.sendAcc >= SEND_DT) {
    state.sendAcc -= SEND_DT;
    const msg = {
      seq: state.seq++,
      dt: SEND_DT,
      ...look,
    };
    state.transport.send("input", msg);
  }
}

let last = performance.now();
function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;

  if (running) {
    // Send inputs and advance camera smoothing.
    for (const s of sessions) {
      if (!s.roomId) continue;
      const look = s.input.sample(dt);
      sendInputs(s, look, dt);
      integrate(s, dt);
      setCameraFromState(s, look, dt);
    }

    entities.updateInterpolated(now);
    hud.setPing(sessions[0]?.clock?.rttMs ?? null);
    renderer.render({ split: sessions.length === 2 });
  }

  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

async function waitFor(pred, timeoutMs) {
  const start = performance.now();
  while (performance.now() - start < timeoutMs) {
    if (pred()) return true;
    await new Promise((r) => setTimeout(r, 25));
  }
  throw new Error("timeout");
}

function loadSettings() {
  const defaults = { invertX: true, invertY: false, sensitivity: 1.0 };
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return { ...defaults };
    const obj = JSON.parse(raw);
    return {
      invertX: !!obj.invertX,
      invertY: !!obj.invertY,
      sensitivity: clamp(Number(obj.sensitivity) || 1.0, 0.5, 3.0),
    };
  } catch {
    return { ...defaults };
  }
}

function saveSettings(s) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {
    // ignore
  }
}

function bindSettingsUI(s) {
  if (el.invertX) el.invertX.checked = !!s.invertX;
  if (el.invertY) el.invertY.checked = !!s.invertY;
  if (el.sens) el.sens.value = String(s.sensitivity);
  if (el.sensVal) el.sensVal.textContent = String(s.sensitivity.toFixed(1));

  el.invertX?.addEventListener("change", () => {
    s.invertX = !!el.invertX.checked;
    saveSettings(s);
  });
  el.invertY?.addEventListener("change", () => {
    s.invertY = !!el.invertY.checked;
    saveSettings(s);
  });
  el.sens?.addEventListener("input", () => {
    s.sensitivity = clamp(Number(el.sens.value) || 1.0, 0.5, 3.0);
    if (el.sensVal) el.sensVal.textContent = String(s.sensitivity.toFixed(1));
    saveSettings(s);
  });
}
