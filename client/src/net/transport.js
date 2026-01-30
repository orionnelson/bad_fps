export function makeSession({ url, onStatus }) {
  let ws = null;
  let open = false;
  let backoff = 250;
  let closedByUser = false;

  const api = {
    onOpen: null,
    onMessage: null,
    async connect() {
      closedByUser = false;
      onStatus?.("connecting...");
      return new Promise((resolve, reject) => {
        let done = false;
        const timeoutMs = 2500;
        const timer = setTimeout(() => {
          if (done) return;
          done = true;
          try {
            ws?.close();
          } catch {
            // ignore
          }
          reject(new Error("ws connect timeout"));
        }, timeoutMs);

        try {
          ws = new WebSocket(url);
        } catch (e) {
          clearTimeout(timer);
          done = true;
          reject(e);
          return;
        }

        ws.onopen = () => {
          if (done) return;
          done = true;
          clearTimeout(timer);
          open = true;
          backoff = 250;
          onStatus?.("connected");
          try {
            api.onOpen?.();
          } catch {
            // ignore
          }
          resolve();
        };
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            api.onMessage?.(msg.type, msg.data);
          } catch {
            // ignore
          }
        };
        ws.onclose = () => {
          open = false;
          onStatus?.("disconnected");
          if (!done) {
            done = true;
            clearTimeout(timer);
            reject(new Error("ws closed before open"));
          }
          if (!closedByUser) {
            setTimeout(() => api.connect().catch(() => {}), backoff);
            backoff = Math.min(3000, backoff * 1.6);
          }
        };
        ws.onerror = () => {
          // Some browsers fire error without close; fail initial connect.
          if (!done && !open) {
            done = true;
            clearTimeout(timer);
            reject(new Error("ws error"));
          }
        };
      });
    },
    send(type, data) {
      if (!open || !ws) return;
      ws.send(JSON.stringify({ type, data }));
    },
    close() {
      closedByUser = true;
      try {
        ws?.close();
      } catch {}
      ws = null;
      open = false;
    },
  };

  return api;
}
