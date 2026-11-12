"use client";

import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

import { QuantumCapsule } from "@/components/landing/quantum-capsule";

// Reference frame the scene was composed for; the renderer scales to the container while
// keeping this aspect so the capsule is framed the same on every viewport.
const BASE_WIDTH = 820;
const BASE_HEIGHT = 620;

const FLUID_W = 1024;
const FLUID_H = 256;

export function QuantumCapsule3D() {
  const mountRef = useRef<HTMLDivElement | null>(null);
  // WebGL can be unavailable (software rendering, blocked, old devices): fall back to the
  // CSS/2D capsule instead of failing the whole landing page.
  const [webglFailed, setWebglFailed] = useState(false);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // ── Scene, camera, renderer ─────────────────────────────────────────────
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, BASE_WIDTH / BASE_HEIGHT, 0.1, 100);
    camera.position.set(0, 0, 21);
    camera.lookAt(0, 0, 0);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "default",
      });
    } catch {
      // Swap to the 2D fallback on the next tick rather than synchronously in the effect.
      queueMicrotask(() => setWebglFailed(true));
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.9;
    container.appendChild(renderer.domElement);

    const fitToContainer = () => {
      const width = container.clientWidth || BASE_WIDTH;
      const height = container.clientHeight || Math.round((width * BASE_HEIGHT) / BASE_WIDTH);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    fitToContainer();

    // Image-based lighting: brushed metal and glass only read as real when they have
    // something to reflect.
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envTexture = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = envTexture;

    // ── Procedural textures ─────────────────────────────────────────────────
    // Fine knurl (diamond cross-hatch) for the grip sections.
    const knurlCanvas = document.createElement("canvas");
    knurlCanvas.width = 256;
    knurlCanvas.height = 256;
    const kCtx = knurlCanvas.getContext("2d");
    if (kCtx) {
      const img = kCtx.createImageData(256, 256);
      for (let y = 0; y < 256; y++) {
        for (let x = 0; x < 256; x++) {
          const v = Math.floor(
            (Math.sin((x + y) * 0.5) * Math.sin((x - y) * 0.5) * 0.5 + 0.5) * 255,
          );
          const i = (y * 256 + x) * 4;
          img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
          img.data[i + 3] = 255;
        }
      }
      kCtx.putImageData(img, 0, 0);
    }
    const knurlBump = new THREE.CanvasTexture(knurlCanvas);
    knurlBump.wrapS = knurlBump.wrapT = THREE.RepeatWrapping;
    knurlBump.repeat.set(24, 4);

    // Fine brushed-metal streaks for the polished rings.
    const brushCanvas = document.createElement("canvas");
    brushCanvas.width = 512;
    brushCanvas.height = 64;
    const bCtx = brushCanvas.getContext("2d");
    if (bCtx) {
      bCtx.fillStyle = "#808080";
      bCtx.fillRect(0, 0, 512, 64);
      for (let i = 0; i < 1400; i++) {
        const y = Math.random() * 64;
        const x = Math.random() * 512;
        const tone = Math.random() < 0.5 ? 255 : 0;
        bCtx.strokeStyle = `rgba(${tone},${tone},${tone},0.08)`;
        bCtx.beginPath();
        bCtx.moveTo(x, y);
        bCtx.lineTo(x + 40 + Math.random() * 200, y);
        bCtx.stroke();
      }
    }
    const brushRough = new THREE.CanvasTexture(brushCanvas);
    brushRough.wrapS = brushRough.wrapT = THREE.RepeatWrapping;
    brushRough.repeat.set(1, 6);

    // Laser-etched graduations on the glass.
    const scaleCanvas = document.createElement("canvas");
    scaleCanvas.width = 1024;
    scaleCanvas.height = 64;
    const sCtx = scaleCanvas.getContext("2d");
    if (sCtx) {
      sCtx.fillStyle = "rgba(255,255,255,0.85)";
      sCtx.font = "500 9px ui-monospace, monospace";
      sCtx.textAlign = "center";
      for (let i = 0; i <= 80; i++) {
        const x = 60 + (i / 80) * 904;
        const major = i % 10 === 0;
        sCtx.fillRect(x - 0.5, 0, 1, major ? 14 : i % 5 === 0 ? 9 : 5);
        if (major) sCtx.fillText(`${i}`, x, 26);
      }
    }
    const scaleTex = new THREE.CanvasTexture(scaleCanvas);
    scaleTex.wrapS = scaleTex.wrapT = THREE.ClampToEdgeWrapping;

    // ── Plasma core (animated canvas texture) ───────────────────────────────
    const fluidCanvas = document.createElement("canvas");
    fluidCanvas.width = FLUID_W;
    fluidCanvas.height = FLUID_H;
    const fCtx = fluidCanvas.getContext("2d");
    const fluidTexture = new THREE.CanvasTexture(fluidCanvas);
    fluidTexture.wrapS = THREE.RepeatWrapping;
    fluidTexture.wrapT = THREE.ClampToEdgeWrapping;
    fluidTexture.colorSpace = THREE.SRGBColorSpace;

    const particles = Array.from({ length: 140 }, () => ({
      x: Math.random() * FLUID_W,
      y: FLUID_H * 0.5 + (Math.random() - 0.5) * FLUID_H * 0.55,
      vx: 0.25 + Math.random() * 0.6,
      r: Math.random() < 0.08 ? 1.8 : 0.5 + Math.random() * 0.8,
      a: 0.35 + Math.random() * 0.5,
      lime: Math.random() < 0.6,
    }));

    // ── Geometry ────────────────────────────────────────────────────────────
    const capsuleGroup = new THREE.Group();
    capsuleGroup.scale.setScalar(0.92);
    scene.add(capsuleGroup);

    const R = 0.9; // tube radius
    const L = 10; // tube length

    const knurledMat = new THREE.MeshStandardMaterial({
      color: 0x5f666f,
      metalness: 1.0,
      roughness: 0.46,
      bumpMap: knurlBump,
      bumpScale: 0.03,
      envMapIntensity: 0.55,
    });
    const polishedMat = new THREE.MeshStandardMaterial({
      color: 0xaab0b8,
      metalness: 1.0,
      roughness: 0.24,
      roughnessMap: brushRough,
      envMapIntensity: 0.7,
    });
    const darkSteelMat = new THREE.MeshStandardMaterial({
      color: 0x2b3038,
      metalness: 0.9,
      roughness: 0.35,
      envMapIntensity: 0.5,
    });
    const gasketMat = new THREE.MeshStandardMaterial({
      color: 0x0b0d10,
      metalness: 0.0,
      roughness: 0.85,
    });

    // Glass: clear coated shell; opacity rather than transmission (transmission samples an
    // empty buffer on an alpha canvas and fogs the tube).
    const glassMat = new THREE.MeshPhysicalMaterial({
      color: 0xf4f7fa,
      metalness: 0,
      roughness: 0.02,
      clearcoat: 1,
      clearcoatRoughness: 0.02,
      envMapIntensity: 0.45,
      transparent: true,
      opacity: 0.16,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const glass = new THREE.Mesh(new THREE.CylinderGeometry(R, R, L, 96, 1, true), glassMat);
    glass.renderOrder = 3;
    capsuleGroup.add(glass);

    const etch = new THREE.Mesh(
      new THREE.CylinderGeometry(R + 0.004, R + 0.004, L * 0.84, 64, 1, true),
      new THREE.MeshBasicMaterial({
        map: scaleTex,
        transparent: true,
        opacity: 0.45,
        side: THREE.FrontSide,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    etch.rotation.y = Math.PI * 0.45;
    etch.renderOrder = 2;
    capsuleGroup.add(etch);

    // Core: an inner cylinder carrying the plasma texture plus a soft axial haze.
    const core = new THREE.Mesh(
      new THREE.CylinderGeometry(R * 0.78, R * 0.78, L * 0.96, 64, 1, true),
      new THREE.MeshBasicMaterial({
        map: fluidTexture,
        transparent: true,
        opacity: 1,
        side: THREE.BackSide,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    core.renderOrder = 1;
    capsuleGroup.add(core);
    // Front pass of the same texture, lighter, so filaments read through the glass.
    const coreFront = new THREE.Mesh(
      new THREE.CylinderGeometry(R * 0.78, R * 0.78, L * 0.96, 64, 1, true),
      new THREE.MeshBasicMaterial({
        map: fluidTexture,
        transparent: true,
        opacity: 0.6,
        side: THREE.FrontSide,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    coreFront.renderOrder = 2;
    capsuleGroup.add(coreFront);

    const innerWall = new THREE.Mesh(
      new THREE.CylinderGeometry(R * 0.97, R * 0.97, L, 64, 1, true),
      new THREE.MeshBasicMaterial({
        color: 0x05070c,
        transparent: true,
        opacity: 0.6,
        side: THREE.BackSide,
        depthWrite: false,
      }),
    );
    innerWall.renderOrder = -1;
    capsuleGroup.add(innerWall);

    const haze = new THREE.Mesh(
      new THREE.CylinderGeometry(R * 0.5, R * 0.5, L * 0.9, 32, 1, true),
      new THREE.MeshBasicMaterial({
        color: 0xffb347,
        transparent: true,
        opacity: 0.1,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    );
    haze.renderOrder = 0;
    capsuleGroup.add(haze);

    // Machined end caps: gasket → collar → knurled grip → bezel → recessed face.
    const makeCap = (top: boolean) => {
      const g = new THREE.Group();
      const d = top ? 1 : -1;
      const add = (geom: THREE.BufferGeometry, mat: THREE.Material, y: number) => {
        const m = new THREE.Mesh(geom, mat);
        m.position.y = d * y;
        g.add(m);
        return m;
      };
      add(new THREE.CylinderGeometry(R + 0.015, R + 0.015, 0.12, 64), gasketMat, 0.06);
      add(new THREE.CylinderGeometry(R + 0.11, R + 0.05, 0.3, 96), polishedMat, 0.27);
      add(new THREE.CylinderGeometry(R + 0.16, R + 0.16, 1.15, 96), knurledMat, 1.0);
      add(new THREE.CylinderGeometry(R + 0.09, R + 0.16, 0.22, 96), polishedMat, 1.68);
      add(new THREE.CylinderGeometry(R + 0.09, R + 0.09, 0.16, 96), polishedMat, 1.87);
      // Recessed machined face with a dark centre boss.
      add(new THREE.CylinderGeometry(R * 0.72, R + 0.09, 0.08, 96), darkSteelMat, 1.99);
      add(new THREE.CylinderGeometry(R * 0.3, R * 0.3, 0.1, 48), polishedMat, 2.04);
      // Small latch block on the top cap.
      if (top) {
        const latch = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.22, 0.46), polishedMat);
        latch.position.set(0, 1.0, R + 0.18);
        g.add(latch);
        const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.4, 24), darkSteelMat);
        pin.rotation.z = Math.PI / 2;
        pin.position.set(0, 1.0, R + 0.3);
        g.add(pin);
      }
      return g;
    };
    const topCap = makeCap(true);
    topCap.position.y = L / 2;
    const bottomCap = makeCap(false);
    bottomCap.position.y = -L / 2;
    capsuleGroup.add(topCap, bottomCap);

    // ── Lighting (restrained; the environment does most of the work) ────────
    const limeLight = new THREE.PointLight(0xc4ff00, 2.2, 6, 2);
    limeLight.position.set(0, 0.8, 0);
    const amberLight = new THREE.PointLight(0xff8a1f, 1.8, 6, 2);
    amberLight.position.set(0, -0.8, 0);
    capsuleGroup.add(limeLight, amberLight);

    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(-6, 10, 10);
    const rim = new THREE.DirectionalLight(0xcfe0ff, 1.1);
    rim.position.set(8, -4, -6);
    const warm = new THREE.DirectionalLight(0xb4202f, 0.8);
    warm.position.set(2, -8, -4);
    scene.add(key, rim, warm, new THREE.AmbientLight(0x1c2230, 0.5));

    // ── Orientation and motion ──────────────────────────────────────────────
    capsuleGroup.rotation.set(0.12, 0.18, -0.71);
    let targetRotX = 0.12;
    let targetRotY = 0.18;
    const onMouseMove = (e: MouseEvent) => {
      const r = container.getBoundingClientRect();
      const mx = (e.clientX - r.left) / r.width - 0.5;
      const my = (e.clientY - r.top) / r.height - 0.5;
      targetRotY = 0.18 + mx * 0.22;
      targetRotX = 0.12 - my * 0.18;
    };

    let t = 0;

    const ribbon = (
      ctx: CanvasRenderingContext2D,
      f: (x: number) => number,
      width: number,
      style: string,
      blur: number,
    ) => {
      ctx.beginPath();
      for (let x = 0; x <= FLUID_W; x += 6) {
        const y = f(x);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.lineWidth = width;
      ctx.strokeStyle = style;
      ctx.filter = blur ? `blur(${blur}px)` : "none";
      ctx.stroke();
    };

    const paintFluid = () => {
      if (!fCtx) return;
      const ctx = fCtx;
      const cy = FLUID_H / 2;
      ctx.globalCompositeOperation = "source-over";
      ctx.filter = "none";
      ctx.clearRect(0, 0, FLUID_W, FLUID_H);

      // Soft axial ambience, lime at the core fading to amber at the walls.
      const g = ctx.createLinearGradient(0, 0, 0, FLUID_H);
      g.addColorStop(0, "rgba(255,110,20,0)");
      g.addColorStop(0.3, "rgba(255,140,30,0.05)");
      g.addColorStop(0.5, "rgba(200,255,40,0.14)");
      g.addColorStop(0.7, "rgba(255,140,30,0.05)");
      g.addColorStop(1, "rgba(255,110,20,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, FLUID_W, FLUID_H);

      ctx.globalCompositeOperation = "lighter";

      const limeF = (x: number) =>
        cy + Math.sin(x * 0.011 - t * 0.9) * 46 + Math.sin(x * 0.027 + t * 0.6) * 14;
      const amberF = (x: number) =>
        cy + Math.sin(x * 0.0095 + t * 0.7 + Math.PI) * 50 + Math.cos(x * 0.022 - t * 0.5) * 12;
      const whiteF = (x: number) => (limeF(x) + amberF(x)) * 0.5;

      ribbon(ctx, amberF, 28, "rgba(255,120,20,0.34)", 14);
      ribbon(ctx, amberF, 5, "rgba(255,175,55,0.85)", 2.5);
      ribbon(ctx, limeF, 32, "rgba(190,255,40,0.4)", 16);
      ribbon(ctx, limeF, 4.5, "rgba(205,255,70,0.95)", 2);
      ribbon(ctx, whiteF, 1.2, "rgba(255,250,215,0.5)", 0);

      ctx.filter = "none";
      for (const p of particles) {
        p.x += p.vx;
        if (p.x > FLUID_W + 8) p.x = -8;
        const y = p.y + Math.sin(p.x * 0.015 + t * 1.1) * 10;
        ctx.fillStyle = p.lime ? `rgba(215,255,80,${p.a})` : `rgba(255,170,60,${p.a})`;
        ctx.beginPath();
        ctx.arc(p.x, y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
      fluidTexture.needsUpdate = true;
    };

    const renderFrame = () => {
      t += 0.016;
      capsuleGroup.rotation.x += (targetRotX - capsuleGroup.rotation.x) * 0.04;
      capsuleGroup.rotation.y += (targetRotY - capsuleGroup.rotation.y) * 0.04;
      capsuleGroup.position.y = Math.sin(t * 0.45) * 0.07;
      fluidTexture.offset.x = (t * 0.02) % 1;
      paintFluid();
      limeLight.intensity = 2.2 + Math.sin(t * 1.4) * 0.4;
      amberLight.intensity = 1.8 + Math.cos(t * 1.1) * 0.3;
      renderer.render(scene, camera);
    };

    // Animate only while on screen.
    let animId = 0;
    let visible = true;
    const animate = () => {
      animId = 0;
      if (!visible) return;
      renderFrame();
      animId = requestAnimationFrame(animate);
    };
    const start = () => {
      if (animId === 0) animId = requestAnimationFrame(animate);
    };
    const stop = () => {
      if (animId !== 0) {
        cancelAnimationFrame(animId);
        animId = 0;
      }
    };

    const resizeObserver = new ResizeObserver(() => {
      fitToContainer();
      if (reducedMotion) renderFrame();
    });
    resizeObserver.observe(container);

    let intersectionObserver: IntersectionObserver | undefined;
    if (reducedMotion) {
      renderFrame();
    } else {
      window.addEventListener("mousemove", onMouseMove);
      intersectionObserver = new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        if (visible) start();
        else stop();
      });
      intersectionObserver.observe(container);
      start();
    }

    return () => {
      stop();
      intersectionObserver?.disconnect();
      resizeObserver.disconnect();
      window.removeEventListener("mousemove", onMouseMove);
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh) {
          obj.geometry.dispose();
          const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
          for (const m of mats) m.dispose();
        }
      });
      knurlBump.dispose();
      brushRough.dispose();
      scaleTex.dispose();
      fluidTexture.dispose();
      envTexture.dispose();
      pmrem.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) container.removeChild(renderer.domElement);
    };
  }, []);

  if (webglFailed) {
    return <QuantumCapsule />;
  }

  return (
    <div className="pointer-events-auto relative flex w-full items-center justify-center overflow-visible select-none">
      {/* Soft ambient bloom behind the tube */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-[12%] rounded-full bg-gradient-to-r from-[#C4FF00]/14 via-[#FF9900]/10 to-transparent opacity-80 blur-3xl"
      />
      <div
        ref={mountRef}
        aria-hidden
        className="relative aspect-[820/620] w-full max-w-[820px] overflow-visible [&>canvas]:h-full [&>canvas]:w-full"
      />
    </div>
  );
}
