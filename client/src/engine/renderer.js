import * as THREE from "https://unpkg.com/three@0.160.0/build/three.module.js";

const VIEWMODEL_LAYER_BASE = 10;
const P1_BODY_LAYER = 1;
const P2_BODY_LAYER = 2;

function makeLightRig(scene) {
  scene.add(new THREE.AmbientLight(0xffffff, 0.45));
  const key = new THREE.DirectionalLight(0xfff4d8, 1.2);
  key.position.set(8, 14, 6);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x7bd7ff, 0.55);
  rim.position.set(-10, 6, -12);
  scene.add(rim);
}

export class Renderer {
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.Fog(0x0b1020, 18, 220);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    this.renderer.setClearColor(0x0b1020, 1);

    // Reduce visible banding in fog/gradients.
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;

    container.appendChild(this.renderer.domElement);

    this.cameras = [new THREE.PerspectiveCamera(75, 1, 0.05, 250), new THREE.PerspectiveCamera(75, 1, 0.05, 250)];
    // Add cameras to scene so we can attach a simple view-model.
    this.scene.add(this.cameras[0]);
    this.scene.add(this.cameras[1]);

    this._makeViewModels();

    this.setSplitMode(false);

    makeLightRig(this.scene);
    this._buildArena();

    const onResize = () => this.resize();
    window.addEventListener("resize", onResize);
    this.resize();
  }

  _makeViewModels() {
    // Minimal gun view-model.
    const matGun = new THREE.MeshStandardMaterial({
      color: 0x1d2a44,
      roughness: 0.35,
      metalness: 0.25,
      emissive: 0x02040a,
    });
    const matAccent = new THREE.MeshStandardMaterial({
      color: 0xffd166,
      roughness: 0.2,
      metalness: 0.45,
      emissive: 0x110a00,
    });
    // Always draw on top.
    matGun.depthTest = false;
    matGun.depthWrite = false;
    matAccent.depthTest = false;
    matAccent.depthWrite = false;

    this.viewModels = [];
    for (let i = 0; i < this.cameras.length; i++) {
      const layer = VIEWMODEL_LAYER_BASE + i;
      const gun = new THREE.Group();
      gun.layers.set(layer);

      const body = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.12, 0.52), matGun);
      body.layers.set(layer);
      body.position.set(0.18, -0.18, -0.55);

      const grip = new THREE.Mesh(new THREE.BoxGeometry(0.10, 0.18, 0.16), matGun);
      grip.layers.set(layer);
      grip.position.set(0.16, -0.28, -0.40);
      grip.rotation.x = 0.25;

      const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.36, 12), matAccent);
      barrel.layers.set(layer);
      barrel.rotation.x = Math.PI / 2;
      barrel.position.set(0.20, -0.16, -0.86);

      gun.add(body);
      gun.add(grip);
      gun.add(barrel);
      gun.renderOrder = 999;

      this.cameras[i].add(gun);
      this.viewModels.push(gun);
    }
  }

  setSplitMode(split) {
    this._split = !!split;

    // Camera 1 sees world + other player body + its viewmodel.
    const c0 = this.cameras[0];
    c0.layers.enable(0);
    c0.layers.enable(VIEWMODEL_LAYER_BASE);
    c0.layers.disable(P1_BODY_LAYER);
    if (this._split) c0.layers.enable(P2_BODY_LAYER);
    else c0.layers.disable(P2_BODY_LAYER);

    // Camera 2 sees world + other player body + its viewmodel.
    const c1 = this.cameras[1];
    c1.layers.enable(0);
    c1.layers.enable(VIEWMODEL_LAYER_BASE + 1);
    c1.layers.disable(P2_BODY_LAYER);
    if (this._split) c1.layers.enable(P1_BODY_LAYER);
    else c1.layers.disable(P1_BODY_LAYER);

    // Also set each viewmodel group to its camera layer (belt & suspenders).
    if (this.viewModels?.[0]) this.viewModels[0].traverse((o) => o.layers.set(VIEWMODEL_LAYER_BASE));
    if (this.viewModels?.[1]) this.viewModels[1].traverse((o) => o.layers.set(VIEWMODEL_LAYER_BASE + 1));
  }

  _buildArena() {
    const floorGeo = new THREE.PlaneGeometry(260, 260, 1, 1);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x0e1b2f,
      roughness: 0.95,
      metalness: 0.0,
    });
    floorMat.dithering = true;
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0;
    this.scene.add(floor);

    const grid = new THREE.GridHelper(260, 130, 0x2b3a5a, 0x18233a);
    grid.position.y = 0.01;
    this.scene.add(grid);

    // Simple obstacles to match server map roughly.
    const boxMat = new THREE.MeshStandardMaterial({ color: 0x1b2b4a, roughness: 0.9, metalness: 0.05 });
    boxMat.dithering = true;
    const boxes = [
      { pos: [0, 1, 0], size: [10, 2, 10] },
      { pos: [-12, 1, -10], size: [8, 2, 3] },
      { pos: [12, 1, 10], size: [8, 2, 3] },
      { pos: [-15, 1, 15], size: [3, 2, 10] },
      { pos: [15, 1, -15], size: [3, 2, 10] },
    ];
    for (const b of boxes) {
      const g = new THREE.BoxGeometry(b.size[0], b.size[1], b.size[2]);
      const m = new THREE.Mesh(g, boxMat);
      m.position.set(b.pos[0], b.pos[1], b.pos[2]);
      this.scene.add(m);
    }
  }

  resize() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    this.renderer.setSize(w, h, false);
    for (const cam of this.cameras) {
      cam.aspect = w / h;
      cam.updateProjectionMatrix();
    }
  }

  setCameraPose(slot, pose) {
    const cam = this.cameras[slot];
    if (!cam) return;
    cam.position.set(pose.pos[0], pose.pos[1], pose.pos[2]);
    cam.rotation.order = "YXZ";
    cam.rotation.y = pose.yaw;
    // Convention: pitch > 0 means looking down.
    cam.rotation.x = pose.pitch;
  }

  render({ split }) {
    if (!!split !== this._split) {
      this.setSplitMode(!!split);
    }

    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    this.renderer.setScissorTest(true);

    if (!split) {
      this.cameras[0].aspect = w / h;
      this.cameras[0].updateProjectionMatrix();
      this.renderer.setViewport(0, 0, w, h);
      this.renderer.setScissor(0, 0, w, h);
      this.renderer.render(this.scene, this.cameras[0]);
    } else {
      const halfH = Math.floor(h / 2);
      // Top (P1)
      this.cameras[0].aspect = w / Math.max(1, h - halfH);
      this.cameras[0].updateProjectionMatrix();
      this.renderer.setViewport(0, halfH, w, h - halfH);
      this.renderer.setScissor(0, halfH, w, h - halfH);
      this.renderer.render(this.scene, this.cameras[0]);
      // Bottom (P2)
      this.cameras[1].aspect = w / Math.max(1, halfH);
      this.cameras[1].updateProjectionMatrix();
      this.renderer.setViewport(0, 0, w, halfH);
      this.renderer.setScissor(0, 0, w, halfH);
      this.renderer.render(this.scene, this.cameras[1]);
    }
    this.renderer.setScissorTest(false);
  }
}
