import * as THREE from "https://unpkg.com/three@0.160.0/build/three.module.js";

const INTERP_DELAY_MS = 120;
const STALE_PLAYER_MS = 5000;
const P1_BODY_LAYER = 1;
const P2_BODY_LAYER = 2;

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function lerp3(out, a, b, t) {
  out[0] = lerp(a[0], b[0], t);
  out[1] = lerp(a[1], b[1], t);
  out[2] = lerp(a[2], b[2], t);
  return out;
}

function clamp01(x) {
  return x < 0 ? 0 : x > 1 ? 1 : x;
}

function lerpAngle(a, b, t) {
  let d = b - a;
  while (d > Math.PI) d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return a + d * t;
}

export class Entities {
  constructor(scene) {
    this.scene = scene;

    this.players = new Map(); // playerId -> Mesh
    this.samples = new Map(); // playerId -> [{t,pos,yaw}]
    this.lastSeen = new Map(); // playerId -> t

    this.projectiles = new Map();
    this.pickups = new Map();
    this.fx = [];

    this.localLayers = new Map(); // playerId -> layer

    this._matLocal1 = new THREE.MeshStandardMaterial({ color: 0x2f6bff, roughness: 0.55, metalness: 0.08, emissive: 0x061026 });
    this._matLocal2 = new THREE.MeshStandardMaterial({ color: 0x2f6bff, roughness: 0.55, metalness: 0.08, emissive: 0x061026 });
    this._matOther = new THREE.MeshStandardMaterial({ color: 0x7bd7ff, roughness: 0.7, metalness: 0.05 });
    this._matBot = new THREE.MeshStandardMaterial({ color: 0xffd166, roughness: 0.6, metalness: 0.05 });
    this._matRocket = new THREE.MeshStandardMaterial({ color: 0xff4d6d, roughness: 0.3, metalness: 0.2, emissive: 0x220008 });
    this._matPickupH = new THREE.MeshStandardMaterial({ color: 0xff4d6d, emissive: 0x220008 });
    this._matPickupA = new THREE.MeshStandardMaterial({ color: 0x4dd4ff, emissive: 0x001722 });
    this._matPickupM = new THREE.MeshStandardMaterial({ color: 0x8ef6a1, emissive: 0x002211 });
  }

  setLocalPlayers({ p1Id, p2Id }) {
    this.localLayers.clear();
    if (p1Id) this.localLayers.set(p1Id, P1_BODY_LAYER);
    if (p2Id) this.localLayers.set(p2Id, P2_BODY_LAYER);

    this.localIds = new Set();
    if (p1Id) this.localIds.add(p1Id);
    if (p2Id) this.localIds.add(p2Id);

    // Update existing meshes.
    for (const [id, mesh] of this.players.entries()) {
      this._applyPlayerStyle(id, mesh);
    }
  }

  _applyPlayerStyle(playerId, mesh) {
    const isBot = String(playerId).startsWith("bot_");
    const layer = this.localLayers.get(playerId) || 0;
    mesh.layers.set(layer);

    // Hide your own body in your own camera.
    // P1 body is layer 1 (camera0 disables), P2 body is layer 2 (camera1 disables).

    if (layer === P1_BODY_LAYER) mesh.material = this._matLocal1;
    else if (layer === P2_BODY_LAYER) mesh.material = this._matLocal2;
    else if (isBot) mesh.material = this._matBot;
    else mesh.material = this._matOther;
  }

  _ensurePlayerMesh(playerId) {
    let m = this.players.get(playerId);
    if (m) return m;
    const g = new THREE.CapsuleGeometry(0.35, 1.1, 6, 10);
    m = new THREE.Mesh(g, this._matOther);
    m.castShadow = false;
    m.receiveShadow = false;
    this.scene.add(m);
    this.players.set(playerId, m);
    this._applyPlayerStyle(playerId, m);
    return m;
  }

  _pushSample(playerId, t, pos, yaw) {
    let list = this.samples.get(playerId);
    if (!list) {
      list = [];
      this.samples.set(playerId, list);
    }
    list.push({ t, pos: [pos[0], pos[1], pos[2]], yaw: yaw || 0 });
    while (list.length > 32) list.shift();
  }

  applySnapshot(_localPlayerId, snap) {
    const now = performance.now();

    const players = [];
    if (snap.you && snap.you.playerId && Array.isArray(snap.you.pos)) {
      players.push({ playerId: snap.you.playerId, pos: snap.you.pos, yaw: snap.you.yaw || 0 });
    }
    for (const o of snap.others || []) {
      if (!o || !o.playerId || !Array.isArray(o.pos)) continue;
      players.push({ playerId: o.playerId, pos: o.pos, yaw: o.yaw || 0 });
    }

    for (const p of players) {
      const m = this._ensurePlayerMesh(p.playerId);
      this._applyPlayerStyle(p.playerId, m);
      this._pushSample(p.playerId, now, p.pos, p.yaw);
      this.lastSeen.set(p.playerId, now);
    }

    // Projectiles.
    const seenProj = new Set();
    for (const pr of snap.projectiles || []) {
      if (!pr || !pr.projectileId || !Array.isArray(pr.pos)) continue;
      let m = this.projectiles.get(pr.projectileId);
      if (!m) {
        m = new THREE.Mesh(new THREE.SphereGeometry(0.18, 14, 12), this._matRocket);
        this.scene.add(m);
        this.projectiles.set(pr.projectileId, m);
      }
      m.position.set(pr.pos[0], pr.pos[1], pr.pos[2]);
      seenProj.add(pr.projectileId);
    }
    for (const [id, mesh] of this.projectiles.entries()) {
      if (!seenProj.has(id)) {
        this.scene.remove(mesh);
        this.projectiles.delete(id);
      }
    }

    // Pickups.
    const seenPick = new Set();
    for (const pk of snap.pickups || []) {
      if (!pk || !pk.pickupId || !Array.isArray(pk.pos)) continue;
      let m = this.pickups.get(pk.pickupId);
      if (!m) {
        const g = new THREE.BoxGeometry(0.5, 0.5, 0.5);
        const mat = pk.kind === "armor" ? this._matPickupA : pk.kind === "ammo" ? this._matPickupM : this._matPickupH;
        m = new THREE.Mesh(g, mat);
        this.scene.add(m);
        this.pickups.set(pk.pickupId, m);
      }
      m.visible = !!pk.available;
      m.position.set(pk.pos[0], pk.pos[1] + 0.25, pk.pos[2]);
      m.rotation.y += 0.02;
      seenPick.add(pk.pickupId);
    }
    for (const [id, mesh] of this.pickups.entries()) {
      if (!seenPick.has(id)) {
        this.scene.remove(mesh);
        this.pickups.delete(id);
      }
    }
  }

  updateInterpolated(nowMs) {
    // Expire transient FX.
    for (let i = this.fx.length - 1; i >= 0; i--) {
      if (nowMs >= this.fx[i].until) {
        this.scene.remove(this.fx[i].obj);
        this.fx.splice(i, 1);
      }
    }

    const targetT = nowMs - INTERP_DELAY_MS;
    for (const [id, mesh] of this.players.entries()) {
      const seenAt = this.lastSeen.get(id);
      if (seenAt != null && nowMs - seenAt > STALE_PLAYER_MS) {
        this.scene.remove(mesh);
        this.players.delete(id);
        this.samples.delete(id);
        this.lastSeen.delete(id);
        continue;
      }

      const list = this.samples.get(id);
      if (!list || list.length === 0) continue;

      // Local player bodies render from latest snapshot (no interpolation).
      if (this.localIds?.has(id)) {
        const last = list[list.length - 1];
        const p = last.pos;
        mesh.position.set(p[0], p[1] + 0.9, p[2]);
        mesh.rotation.y = last.yaw;
        continue;
      }
      if (list.length === 1) {
        const p = list[0].pos;
        mesh.position.set(p[0], p[1] + 0.9, p[2]);
        mesh.rotation.y = list[0].yaw;
        continue;
      }

      // Find bracketing samples.
      let a = list[0];
      let b = list[list.length - 1];
      for (let i = 0; i < list.length - 1; i++) {
        if (list[i].t <= targetT && list[i + 1].t >= targetT) {
          a = list[i];
          b = list[i + 1];
          break;
        }
      }

      const span = Math.max(1, b.t - a.t);
      const t = clamp01((targetT - a.t) / span);
      const p = [0, 0, 0];
      lerp3(p, a.pos, b.pos, t);
      mesh.position.set(p[0], p[1] + 0.9, p[2]);
      mesh.rotation.y = lerpAngle(a.yaw, b.yaw, t);
    }
  }

  spawnTracer(origin, dir, length = 18) {
    const a = new THREE.Vector3(origin[0], origin[1], origin[2]);
    const b = new THREE.Vector3(origin[0] + dir[0] * length, origin[1] + dir[1] * length, origin[2] + dir[2] * length);
    const geo = new THREE.BufferGeometry().setFromPoints([a, b]);
    const mat = new THREE.LineBasicMaterial({ color: 0xffd166, transparent: true, opacity: 0.85 });
    const line = new THREE.Line(geo, mat);
    this.scene.add(line);
    this.fx.push({ obj: line, until: performance.now() + 70 });
  }
}
