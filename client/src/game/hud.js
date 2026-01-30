const hpFill = document.getElementById("hpFill");
const hpText = document.getElementById("hpText");
const arFill = document.getElementById("arFill");
const arText = document.getElementById("arText");
const ammoText = document.getElementById("ammoText");
const weaponText = document.getElementById("weaponText");
const hpFill1 = document.getElementById("hpFill1");
const hpText1 = document.getElementById("hpText1");
const arFill1 = document.getElementById("arFill1");
const arText1 = document.getElementById("arText1");
const ammoText1 = document.getElementById("ammoText1");
const weaponText1 = document.getElementById("weaponText1");

const hpFill2 = document.getElementById("hpFill2");
const hpText2 = document.getElementById("hpText2");
const arFill2 = document.getElementById("arFill2");
const arText2 = document.getElementById("arText2");
const ammoText2 = document.getElementById("ammoText2");
const weaponText2 = document.getElementById("weaponText2");
const pingText = document.getElementById("pingText");
const roomText = document.getElementById("roomText");
const scoreText = document.getElementById("scoreText");
let _net = { ackSeq: null, sentSeq: null, serverTick: null };
const feed = document.getElementById("feed");

export class HUD {
  constructor() {
    this._feed = [];
  }

  setVitals({ hp, armor, ammo, weaponId }) {
    const h = Math.max(0, Math.min(100, hp ?? 0));
    const a = Math.max(0, Math.min(75, armor ?? 0));
    hpFill.style.transform = `scaleX(${h / 100})`;
    arFill.style.transform = `scaleX(${a / 75})`;
    hpText.textContent = String(Math.round(h));
    arText.textContent = String(Math.round(a));
    ammoText.textContent = String(ammo ?? "--");
    weaponText.textContent = String(weaponId ?? "--");

    // Also update split P1 if present.
    if (hpFill1) hpFill1.style.transform = `scaleX(${h / 100})`;
    if (arFill1) arFill1.style.transform = `scaleX(${a / 75})`;
    if (hpText1) hpText1.textContent = String(Math.round(h));
    if (arText1) arText1.textContent = String(Math.round(a));
    if (ammoText1) ammoText1.textContent = String(ammo ?? "--");
    if (weaponText1) weaponText1.textContent = String(weaponId ?? "--");
  }

  setVitalsP2({ hp, armor, ammo, weaponId }) {
    const h = Math.max(0, Math.min(100, hp ?? 0));
    const a = Math.max(0, Math.min(75, armor ?? 0));
    if (hpFill2) hpFill2.style.transform = `scaleX(${h / 100})`;
    if (arFill2) arFill2.style.transform = `scaleX(${a / 75})`;
    if (hpText2) hpText2.textContent = String(Math.round(h));
    if (arText2) arText2.textContent = String(Math.round(a));
    if (ammoText2) ammoText2.textContent = String(ammo ?? "--");
    if (weaponText2) weaponText2.textContent = String(weaponId ?? "--");
  }

  setPing(rttMs) {
    pingText.textContent = `ping: ${rttMs == null ? "--" : Math.round(rttMs) + "ms"}`;
  }

  setRoom(roomId) {
    roomText.textContent = `room: ${roomId || "--"}`;
  }

  setScore({ kills, deaths }) {
    const k = kills ?? 0;
    const d = deaths ?? 0;
    const ack = _net.ackSeq == null ? "--" : _net.ackSeq;
    const sent = _net.sentSeq == null ? "--" : _net.sentSeq;
    const dbg = _net.debug || "";
    scoreText.textContent = `kills: ${k} deaths: ${d} | ack: ${ack} sent: ${sent}${dbg}`;
  }

  setNet({ ackSeq, sentSeq, serverTick }) {
    _net = { ackSeq, sentSeq, serverTick, debug: _net.debug };
  }

  setDebug(text) {
    _net.debug = text ? ` | ${text}` : "";
  }

  pushFeed(text) {
    this._feed.unshift({ t: performance.now(), text });
    this._feed = this._feed.slice(0, 6);
    this._renderFeed();
  }

  _renderFeed() {
    const now = performance.now();
    this._feed = this._feed.filter((e) => now - e.t < 5000);
    feed.innerHTML = this._feed.map((e) => `<div>${escapeHtml(e.text)}</div>`).join("");
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
