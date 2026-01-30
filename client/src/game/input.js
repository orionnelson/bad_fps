function clamp(x, lo, hi) {
  return x < lo ? lo : x > hi ? hi : x;
}

function wrapAngle(a) {
  while (a > Math.PI) a -= Math.PI * 2;
  while (a < -Math.PI) a += Math.PI * 2;
  return a;
}

let _installed = false;
let _viewport = null;
const _keys = new Set();
const _mouseButtons = new Set();
let _pointerLocked = false;
let _mouseDx = 0;
let _mouseDy = 0;

// Debug counters.
let _dbgKeyDown = 0;
let _dbgKeyUp = 0;
let _dbgLastKey = "";

const CONTROLLED_CODES = new Set([
  "KeyW",
  "KeyA",
  "KeyS",
  "KeyD",
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "Space",
  "ShiftLeft",
  "ShiftRight",
  "Enter",
  "Slash",
  "ControlRight",
  "Semicolon",
  "KeyI",
  "KeyJ",
  "KeyK",
  "KeyL",
  "KeyR",
  "Digit1",
  "Digit2",
  "Digit3",
  "Numpad1",
  "Numpad2",
  "Numpad3",
]);

function installGlobalListeners(viewport) {
  if (_installed) return;
  _installed = true;
  _viewport = viewport;

  window.addEventListener(
    "keydown",
    (e) => {
      const tag = e?.target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (CONTROLLED_CODES.has(e.code)) {
        try {
          e.preventDefault();
        } catch {
          // ignore
        }
      }
      _keys.add(e.code);
      _dbgKeyDown++;
      _dbgLastKey = e.code;
    },
    { capture: true, passive: false }
  );

  window.addEventListener(
    "keyup",
    (e) => {
      const tag = e?.target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (CONTROLLED_CODES.has(e.code)) {
        try {
          e.preventDefault();
        } catch {
          // ignore
        }
      }
      _keys.delete(e.code);
      _dbgKeyUp++;
      _dbgLastKey = e.code;
    },
    { capture: true, passive: false }
  );

  viewport.addEventListener("mousedown", (e) => {
    _mouseButtons.add(e.button);
  });

  window.addEventListener("mouseup", (e) => {
    _mouseButtons.delete(e.button);
  });

  window.addEventListener("mousemove", (e) => {
    if (!_pointerLocked) return;
    _mouseDx += e.movementX;
    _mouseDy += e.movementY;
  });

  document.addEventListener("pointerlockchange", () => {
    _pointerLocked = document.pointerLockElement === _viewport;
    _mouseDx = 0;
    _mouseDy = 0;
  });

  // Touch controls (mobile)
  const touchRoot = document.getElementById("touch");
  const elMove = document.getElementById("touchMove");
  const elStick = document.getElementById("touchStick");
  const elLook = document.getElementById("touchLook");
  const btnFire = document.getElementById("touchFire");
  const btnJump = document.getElementById("touchJump");
  const btnReload = document.getElementById("touchReload");

  const isMobile = ("ontouchstart" in window) || (navigator.maxTouchPoints || 0) > 0;
  if (touchRoot) {
    touchRoot.setAttribute("aria-hidden", isMobile ? "false" : "true");
  }

  if (!isMobile || !elMove || !elStick || !elLook || !btnFire || !btnJump || !btnReload) return;

  let moveActive = false;
  let moveId = -1;
  let moveCx = 0;
  let moveCy = 0;
  const moveR = 64;

  let lookActive = false;
  let lookId = -1;
  let lookLastX = 0;
  let lookLastY = 0;

  // Public touch state
  window.__touch = window.__touch || {
    moveX: 0,
    moveY: 0,
    fire: false,
    jump: false,
    reload: false,
    lookDx: 0,
    lookDy: 0,
  };

  function setStick(dx, dy) {
    const x = clamp(dx, -moveR, moveR);
    const y = clamp(dy, -moveR, moveR);
    elStick.style.transform = `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`;
  }

  elMove.addEventListener("pointerdown", (e) => {
    moveActive = true;
    moveId = e.pointerId;
    elMove.setPointerCapture(moveId);
    const r = elMove.getBoundingClientRect();
    moveCx = r.left + r.width * 0.5;
    moveCy = r.top + r.height * 0.5;
    setStick(0, 0);
  });

  elMove.addEventListener("pointermove", (e) => {
    if (!moveActive || e.pointerId !== moveId) return;
    const dx = e.clientX - moveCx;
    const dy = e.clientY - moveCy;
    const len = Math.hypot(dx, dy) || 1;
    const nx = (len > moveR ? dx / len : dx / moveR);
    const ny = (len > moveR ? dy / len : dy / moveR);
    window.__touch.moveX = clamp(nx, -1, 1);
    window.__touch.moveY = clamp(-ny, -1, 1);
    setStick(clamp(dx, -moveR, moveR), clamp(dy, -moveR, moveR));
  });

  function endMove() {
    moveActive = false;
    moveId = -1;
    window.__touch.moveX = 0;
    window.__touch.moveY = 0;
    setStick(0, 0);
  }

  elMove.addEventListener("pointerup", (e) => {
    if (e.pointerId !== moveId) return;
    endMove();
  });

  elMove.addEventListener("pointercancel", (e) => {
    if (e.pointerId !== moveId) return;
    endMove();
  });

  elLook.addEventListener("pointerdown", (e) => {
    lookActive = true;
    lookId = e.pointerId;
    elLook.setPointerCapture(lookId);
    lookLastX = e.clientX;
    lookLastY = e.clientY;
  });

  elLook.addEventListener("pointermove", (e) => {
    if (!lookActive || e.pointerId !== lookId) return;
    const dx = e.clientX - lookLastX;
    const dy = e.clientY - lookLastY;
    lookLastX = e.clientX;
    lookLastY = e.clientY;
    window.__touch.lookDx += dx;
    window.__touch.lookDy += dy;
  });

  function endLook() {
    lookActive = false;
    lookId = -1;
  }

  elLook.addEventListener("pointerup", (e) => {
    if (e.pointerId !== lookId) return;
    endLook();
  });

  elLook.addEventListener("pointercancel", (e) => {
    if (e.pointerId !== lookId) return;
    endLook();
  });

  btnFire.addEventListener("pointerdown", () => {
    window.__touch.fire = true;
  });
  btnFire.addEventListener("pointerup", () => {
    window.__touch.fire = false;
  });
  btnFire.addEventListener("pointercancel", () => {
    window.__touch.fire = false;
  });

  btnJump.addEventListener("pointerdown", () => {
    window.__touch.jump = true;
  });
  btnJump.addEventListener("pointerup", () => {
    window.__touch.jump = false;
  });
  btnJump.addEventListener("pointercancel", () => {
    window.__touch.jump = false;
  });

  btnReload.addEventListener("pointerdown", () => {
    window.__touch.reload = true;
  });
  btnReload.addEventListener("pointerup", () => {
    // one-shot
    window.__touch.reload = false;
  });
  btnReload.addEventListener("pointercancel", () => {
    window.__touch.reload = false;
  });
}

function isDown(code) {
  return _keys.has(code);
}

function anyDown(codes) {
  for (const c of codes) if (_keys.has(c)) return true;
  return false;
}

function consumeMouseDeltas() {
  const dx = _mouseDx;
  const dy = _mouseDy;
  _mouseDx = 0;
  _mouseDy = 0;
  return { dx, dy };
}

export function createInput({ mode, viewport, settings }) {
  installGlobalListeners(viewport);

  const cfg = settings || { invertX: true, invertY: false, sensitivity: 1.0 };

  let yaw = 0;
  let pitch = 0;
  let weaponId = "pistol";

  const maps = {
    solo: {
      move: { f: ["KeyW"], b: ["KeyS"], l: ["KeyA"], r: ["KeyD"] },
      sprint: ["ShiftLeft", "ShiftRight"],
      jump: ["Space"],
      reload: ["KeyR"],
      w1: ["Digit1"],
      w2: ["Digit2"],
      w3: ["Digit3"],
      fire: { mouse: true },
      look: { mouse: true },
    },
    p1: {
      move: { f: ["KeyW"], b: ["KeyS"], l: ["KeyA"], r: ["KeyD"] },
      sprint: ["ShiftLeft"],
      jump: ["Space"],
      reload: ["KeyR"],
      w1: ["Digit1"],
      w2: ["Digit2"],
      w3: ["Digit3"],
      fire: { mouse: true },
      look: { mouse: true },
    },
    p2: {
      move: { f: ["ArrowUp"], b: ["ArrowDown"], l: ["ArrowLeft"], r: ["ArrowRight"] },
      sprint: ["ShiftRight"],
      jump: ["Enter"],
      reload: ["Slash"],
      w1: ["Numpad1", "Digit7"],
      w2: ["Numpad2", "Digit8"],
      w3: ["Numpad3", "Digit9"],
      fire: { keys: ["Semicolon"] },
      look: {
        keys: {
          left: ["KeyJ"],
          right: ["KeyL"],
          up: ["KeyI"],
          down: ["KeyK"],
        },
      },
    },
  };

  const map = maps[mode] || maps.solo;

  const mouseSens = () => 0.0022 * (Number(cfg.sensitivity) || 1.0);
  const invX = () => (cfg.invertX ? -1 : 1);
  const invY = () => (cfg.invertY ? -1 : 1);

  return {
    requestPointerLock() {
      if (mode !== "solo" && mode !== "p1") return;
      viewport.requestPointerLock?.();
    },

    sample(dt) {
      // If the browser lost focus, avoid sticking keys.
      if (!document.hasFocus()) {
        _keys.clear();
        _mouseButtons.clear();
      }

      // Weapons.
      if (anyDown(map.w1)) weaponId = "pistol";
      if (anyDown(map.w2)) weaponId = "shotgun";
      if (anyDown(map.w3)) weaponId = "rocket";

      // Movement.
      let moveX = 0;
      let moveY = 0;
      if (anyDown(map.move.f)) moveY += 1;
      if (anyDown(map.move.b)) moveY -= 1;
      if (anyDown(map.move.l)) moveX -= 1;
      if (anyDown(map.move.r)) moveX += 1;
      moveX = clamp(moveX, -1, 1);
      moveY = clamp(moveY, -1, 1);

      // Touch movement overrides in solo/p1 mode.
      const t = window.__touch;
      if ((mode === "solo" || mode === "p1") && t) {
        if (Math.abs(t.moveX) > 0.01 || Math.abs(t.moveY) > 0.01) {
          moveX = clamp(t.moveX, -1, 1);
          moveY = clamp(t.moveY, -1, 1);
        }
      }

      const sprint = anyDown(map.sprint);
      let jump = anyDown(map.jump);
      const reload = anyDown(map.reload);

      if ((mode === "solo" || mode === "p1") && t) {
        if (t.jump) jump = true;
      }

      // Look.
      if (map.look.mouse) {
        if (mode === "solo" || mode === "p1") {
          if (_pointerLocked) {
            const { dx, dy } = consumeMouseDeltas();
            const s = mouseSens();
            // Convention: positive yaw rotates LEFT, so default (non-inverted) is yaw -= dx*s.
            yaw += (-dx * s) * invX();
            pitch += (dy * s) * invY();
          }

          // Touch look (mobile)
          if (t && (Math.abs(t.lookDx) > 0.001 || Math.abs(t.lookDy) > 0.001)) {
            const dx = t.lookDx;
            const dy = t.lookDy;
            t.lookDx = 0;
            t.lookDy = 0;
            const s = 0.0032 * (Number(cfg.sensitivity) || 1.0);
            yaw += (-dx * s) * invX();
            pitch += (dy * s) * invY();
          }
        }
      } else if (map.look.keys) {
        const ls = 2.0; // rad/sec
        const left = anyDown(map.look.keys.left);
        const right = anyDown(map.look.keys.right);
        const up = anyDown(map.look.keys.up);
        const down = anyDown(map.look.keys.down);

        let yawDelta = 0;
        if (left) yawDelta += ls * dt;
        if (right) yawDelta -= ls * dt;
        yaw += yawDelta * invX();

        let pitchDelta = 0;
        if (up) pitchDelta -= ls * dt;
        if (down) pitchDelta += ls * dt;
        pitch += pitchDelta * invY();
      }

      yaw = wrapAngle(yaw);
      pitch = clamp(pitch, -1.4, 1.4);

      // Fire.
      let fire = false;
      if (map.fire.mouse) {
        fire = _mouseButtons.has(0);
      } else if (map.fire.keys) {
        fire = anyDown(map.fire.keys);
      }

      if ((mode === "solo" || mode === "p1") && t) {
        if (t.fire) fire = true;
      }

      let rel = reload;
      if ((mode === "solo" || mode === "p1") && t) {
        if (t.reload) rel = true;
      }

      return {
        moveX,
        moveY,
        jump,
        sprint,
        yaw,
        pitch,
        fire,
        weaponId,
        reload: rel,
      };
    },

    debug() {
      return {
        hasFocus: !!document.hasFocus?.(),
        pointerLocked: _pointerLocked,
        keysSize: _keys.size,
        lastKey: _dbgLastKey,
        keyDown: _dbgKeyDown,
        keyUp: _dbgKeyUp,
      };
    },
  };
}
