export class ClientClock {
  constructor(transport) {
    this.transport = transport;
    this.rttMs = null;
    this._nextPingAt = 0;
    this._lastPingT = 0;
  }

  tick(nowMs) {
    if (nowMs >= this._nextPingAt) {
      this._nextPingAt = nowMs + 1000;
      this._lastPingT = performance.now();
      this.transport.send("ping", { t: this._lastPingT });
    }
  }

  onPong(data) {
    if (typeof data.t !== "number") return;
    const now = performance.now();
    const rtt = now - data.t;
    this.rttMs = Math.max(0, Math.min(999, rtt));
  }
}
