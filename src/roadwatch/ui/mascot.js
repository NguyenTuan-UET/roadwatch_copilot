// Mascot xe vàng 3D cho màn chờ nạp (index.html, #boot). Cần vendor/three.min.js (r128, chạy offline).
// Dữ liệu: mascot.bin (đỉnh float32 xyz, uv, chỉ số uint16), mascot.json (số đỉnh, đoạn chỉ số từng bộ phận), mascot-tex.jpg.
// window.RoadWatchMascot.start(canvas) → Promise<{wink, stop}>; wink() nháy mắt một lần, stop() dừng vẽ và giải phóng WebGL.
(function () {
  "use strict";
  const TS = 1024, S = 4;
  const EYE = { x: 748.5, y: 843.5, r: 21 };   // mắt trên texture, "lên" là -x

  async function start(canvas) {
    const THREE = window.THREE;
    const [meta, bin, img] = await Promise.all([
      fetch("/ui/mascot.json").then((r) => r.json()),
      fetch("/ui/mascot.bin").then((r) => r.arrayBuffer()),
      new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = "/ui/mascot-tex.jpg"; }),
    ]);
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.outputEncoding = THREE.sRGBEncoding;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
    camera.position.set(5.2, 2.7, 6.6); camera.lookAt(0, 0.95, 0);
    scene.add(new THREE.HemisphereLight(0xffffff, 0xb0b4ba, 0.55));
    const sun = new THREE.DirectionalLight(0xffffff, 0.45); sun.position.set(4, 8, 5); scene.add(sun);

    const texCanvas = document.createElement("canvas"); texCanvas.width = texCanvas.height = TS;
    const tctx = texCanvas.getContext("2d");
    tctx.drawImage(img, 0, 0, TS, TS);
    const baseData = tctx.getImageData(0, 0, TS, TS);
    const texture = new THREE.CanvasTexture(texCanvas);
    texture.encoding = THREE.sRGBEncoding; texture.flipY = false; texture.anisotropy = 8;

    const nv = meta.nv, total = meta.counts.reduce((a, b) => a + b, 0);
    const pos = new Float32Array(bin, 0, nv * 3), uv = new Float32Array(bin, nv * 12, nv * 2), idxAll = new Uint16Array(bin, nv * 20, total);
    const full = new THREE.BufferGeometry();
    full.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    full.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    full.setIndex(new THREE.BufferAttribute(idxAll, 1));
    full.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({ map: texture, emissiveMap: texture, emissive: 0xffffff, emissiveIntensity: 0.62, roughness: 0.55, metalness: 0 });
    const car = new THREE.Group(); scene.add(car);
    const Y0 = -meta.ymin;
    const body = new THREE.Group(); body.scale.setScalar(S); body.position.y = Y0 * S; car.add(body);
    const part = (start, count) => {
      const g = new THREE.BufferGeometry();
      for (const k of ["position", "normal", "uv"]) g.setAttribute(k, full.attributes[k]);
      g.setIndex(new THREE.BufferAttribute(idxAll.subarray(start, start + count), 1));
      return new THREE.Mesh(g, mat);
    };
    let off = 0;
    body.add(part(off, meta.counts[0])); off += meta.counts[0];
    const wheels = [];
    for (let k = 0; k < 4; k++) {
      const c = meta.centers[k], pivot = new THREE.Group();
      pivot.position.set(c[0], c[1], c[2]); body.add(pivot);
      const m = part(off, meta.counts[k + 1]); m.position.set(-c[0], -c[1], -c[2]); pivot.add(m);
      wheels.push(pivot); off += meta.counts[k + 1];
    }

    const shadowCanvas = document.createElement("canvas"); shadowCanvas.width = shadowCanvas.height = 256;
    const sg = shadowCanvas.getContext("2d"), gr = sg.createRadialGradient(128, 128, 10, 128, 128, 128);
    gr.addColorStop(0, "rgba(0,0,0,0.45)"); gr.addColorStop(0.55, "rgba(0,0,0,0.2)"); gr.addColorStop(1, "rgba(0,0,0,0)");
    sg.fillStyle = gr; sg.fillRect(0, 0, 256, 256);
    const shadow = new THREE.Mesh(new THREE.PlaneGeometry(3.4, 5.4), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(shadowCanvas), transparent: true, depthWrite: false }));
    shadow.rotation.x = -Math.PI / 2; shadow.position.y = 0.002; shadow.renderOrder = -1; scene.add(shadow);

    // nháy một mắt: mi trắng trượt xuống đè lên mắt
    function paint(k) {
      tctx.putImageData(baseData, 0, 0);
      if (k > 0) {
        const R = EYE.r + 2, top = EYE.x - R - 2, edge = top + (2 * R + 2) * Math.min(1, k) * 0.62, bow = 10 * Math.min(1, k);
        tctx.save();
        tctx.beginPath(); tctx.arc(EYE.x, EYE.y, R, 0, Math.PI * 2); tctx.clip();
        tctx.fillStyle = "rgb(247,249,247)";
        tctx.beginPath(); tctx.moveTo(top, EYE.y - R - 2); tctx.lineTo(edge - bow * 0.3, EYE.y - R - 2);
        tctx.quadraticCurveTo(edge + bow, EYE.y, edge - bow * 0.3, EYE.y + R + 2); tctx.lineTo(top, EYE.y + R + 2); tctx.closePath(); tctx.fill();
        if (k > 0.97) tctx.fillRect(top, EYE.y - R - 2, 2 * R + 6, 2 * R + 4);
        tctx.restore();
        tctx.strokeStyle = "rgb(24,26,28)"; tctx.lineCap = "round"; tctx.lineWidth = 4.2;
        const ex = Math.min(edge, EYE.x + EYE.r * 0.25);
        tctx.beginPath(); tctx.moveTo(ex - bow * 0.3, EYE.y - R * 0.95); tctx.quadraticCurveTo(ex + bow, EYE.y, ex - bow * 0.3, EYE.y + R * 0.95); tctx.stroke();
      }
      texture.needsUpdate = true;
    }

    // nốt nhạc bay lên khi xe nhảy
    const noteTex = (ch, col) => {
      const c = document.createElement("canvas"); c.width = c.height = 128;
      const g = c.getContext("2d"); g.font = 'bold 104px "Segoe UI Symbol","Noto Sans Symbols 2",sans-serif';
      g.textAlign = "center"; g.textBaseline = "middle"; g.fillStyle = col; g.fillText(ch, 64, 70);
      return new THREE.CanvasTexture(c);
    };
    const noteTexs = [noteTex("♪", "#ff5d8f"), noteTex("♫", "#3d8bfd"), noteTex("♪", "#8a5cf6"), noteTex("★", "#ffb000")];
    const notes = []; let noteIdx = 0;
    for (let i = 0; i < 10; i++) {
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: noteTexs[i % 4], transparent: true, depthWrite: false }));
      sp.visible = false; sp.userData = { life: 0 }; scene.add(sp); notes.push(sp);
    }
    const spawnNote = () => {
      const n = notes[noteIdx++ % notes.length]; n.visible = true;
      n.userData = { life: 1, vx: (Math.random() - 0.5) * 0.8, vz: (Math.random() - 0.5) * 0.8, sp: 0.9 + Math.random() * 0.5 };
      n.position.set((Math.random() - 0.5) * 1.8, 2.3, -0.3);
    };

    function resize() {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    }
    addEventListener("resize", resize); resize();

    const clock = new THREE.Clock();
    let t = 0, lastBeat = 0, blinkT = -1, nextBlink = 1.5, raf = 0, dance = 0, speed = 0, stopped = false;
    function tick() {
      if (stopped) return;
      const dt = Math.min(clock.getDelta(), 0.05); t += dt;
      speed += (1 - speed) * Math.min(1, dt * 3);
      dance += ((reduce ? 0 : 1) - dance) * Math.min(1, dt * 4);
      wheels.forEach((w) => { w.rotation.x += speed * dt * 10; });
      const beat = t * Math.PI * 2 * 1.9, hop = Math.pow(Math.abs(Math.sin(beat / 2)), 1.6);
      car.rotation.z = dance * Math.sin(beat / 4) * 0.09;
      car.rotation.y = dance * Math.sin(beat / 8) * 0.4;
      car.rotation.x = -dance * Math.max(0, Math.sin(beat / 2)) * 0.07;
      car.position.y = dance * hop * 0.28 + Math.abs(Math.sin(car.rotation.x)) * 1.25 + Math.abs(Math.sin(car.rotation.z));
      const sq = dance * (1 - hop) * 0.06;
      car.scale.set(1 + sq * 0.5, 1 - sq, 1 + sq * 0.5);
      body.position.y = Y0 * S + speed * Math.abs(Math.sin(t * 14)) * 0.025;
      const lift = Math.min(1, car.position.y / 0.4);
      shadow.scale.setScalar(1 - 0.25 * lift); shadow.material.opacity = 1 - 0.5 * lift;
      const bi = Math.floor(beat / Math.PI);
      if (dance > 0.5 && bi !== lastBeat && bi % 2 === 0) spawnNote();
      lastBeat = bi;
      notes.forEach((n) => {
        if (!n.visible) return;
        const u = n.userData; u.life -= dt * 0.45;
        if (u.life <= 0) { n.visible = false; return; }
        n.position.y += dt * u.sp; n.position.x += u.vx * dt + Math.sin(t * 4 + u.sp * 9) * dt * 0.3; n.position.z += u.vz * dt;
        n.scale.setScalar(Math.min(0.42, (1 - u.life) * 3)); n.material.opacity = Math.min(1, u.life * 2.5);
      });
      nextBlink -= dt;
      if (nextBlink <= 0 && !reduce) { blinkT = 0; nextBlink = 2.5 + Math.random() * 2; }
      if (blinkT >= 0) {
        blinkT += dt;
        paint(blinkT < 0.12 ? blinkT / 0.12 : blinkT < 0.5 ? 1 : blinkT < 0.64 ? 1 - (blinkT - 0.5) / 0.14 : 0);
        if (blinkT > 0.64) { blinkT = -1; paint(0); }
      }
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    }
    tick();
    return {
      wink() { blinkT = 0; },
      stop() {
        stopped = true; cancelAnimationFrame(raf); removeEventListener("resize", resize);
        renderer.dispose(); renderer.forceContextLoss();
      },
    };
  }

  window.RoadWatchMascot = { start };
})();
