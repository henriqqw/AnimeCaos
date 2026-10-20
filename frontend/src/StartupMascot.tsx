import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

type StartupMascotProps = {
  src: string;
  className: string;
  onLoad: () => void;
  onError: () => void;
  motionScale?: number;
  speed?: number;
};

const imageAspect = 1088 / 1446;
const sourcePath = "/mascots/poses/animecaos-pose-startup-v1.png";

function smoothstep(edge0: number, edge1: number, value: number) {
  const t = THREE.MathUtils.clamp((value - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

type PixelLayers = {
  body: HTMLCanvasElement;
  leftHair: HTMLCanvasElement;
  rightHair: HTMLCanvasElement;
};

type HairMesh = {
  mesh: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial>;
  basePositions: Float32Array;
  side: "left" | "right";
  phase: number;
};

function canvasFromPixels(width: number, height: number, pixels: Uint8ClampedArray) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("Canvas 2D indisponível");
  const image = context.createImageData(width, height);
  image.data.set(pixels);
  context.putImageData(image, 0, 0);
  return canvas;
}

function createPixelLayers(source: HTMLImageElement): PixelLayers {
  const sourceCanvas = document.createElement("canvas");
  const width = source.naturalWidth;
  const height = source.naturalHeight;
  sourceCanvas.width = width;
  sourceCanvas.height = height;
  const context = sourceCanvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("Canvas 2D indisponível");
  context.drawImage(source, 0, 0);
  const sourcePixels = context.getImageData(0, 0, width, height).data;
  const leftSeeds = new Uint8Array(width * height);
  const rightSeeds = new Uint8Array(width * height);

  const interpolate = (points: ReadonlyArray<readonly [number, number]>, y: number) => {
    for (let index = 1; index < points.length; index += 1) {
      const [y1, x1] = points[index - 1];
      const [y2, x2] = points[index];
      if (y <= y2) return x1 + ((x2 - x1) * (y - y1)) / (y2 - y1);
    }
    return points[points.length - 1][1];
  };

  // Esses limites mantêm os recortes na massa lateral do cabelo, longe do rosto.
  const leftBoundary: ReadonlyArray<readonly [number, number]> = [
    [400, 236], [560, 278], [750, 300], [930, 290], [1110, 310], [1320, 375], [1420, 430],
  ];
  const rightBoundary: ReadonlyArray<readonly [number, number]> = [
    [330, 950], [510, 900], [710, 850], [900, 840], [1100, 870], [1300, 940], [1420, 980],
  ];
  const isRedHair = (offset: number) => {
    const red = sourcePixels[offset];
    const green = sourcePixels[offset + 1];
    const blue = sourcePixels[offset + 2];
    return sourcePixels[offset + 3] > 22 && red > 82 && red > green * 1.28 && red > blue * 1.2 && green < 165;
  };

  for (let y = 0; y < height; y += 1) {
    const leftLimit = interpolate(leftBoundary, y);
    const rightLimit = interpolate(rightBoundary, y);
    const rowOffset = y * width;
    for (let x = 0; x < width; x += 1) {
      const index = rowOffset + x;
      if (!isRedHair(index * 4)) continue;
      if (y >= 400 && x < leftLimit) leftSeeds[index] = 1;
      else if (y >= 330 && x > rightLimit) rightSeeds[index] = 1;
    }
  }

  const dilate = (seeds: Uint8Array) => {
    const mask = seeds.slice();
    for (let index = 0; index < seeds.length; index += 1) {
      if (!seeds[index]) continue;
      const x = index % width;
      const y = Math.floor(index / width);
      for (let dy = -2; dy <= 2; dy += 1) {
        const row = y + dy;
        if (row < 0 || row >= height) continue;
        for (let dx = -2; dx <= 2; dx += 1) {
          const column = x + dx;
          if (column >= 0 && column < width) mask[row * width + column] = 1;
        }
      }
    }
    return mask;
  };

  const leftMask = dilate(leftSeeds);
  const rightMask = dilate(rightSeeds);
  const bodyPixels = new Uint8ClampedArray(sourcePixels);
  const leftPixels = new Uint8ClampedArray(width * height * 4);
  const rightPixels = new Uint8ClampedArray(width * height * 4);

  const split = (mask: Uint8Array, output: Uint8ClampedArray, direction: -1 | 1) => {
    for (let index = 0; index < mask.length; index += 1) {
      if (!mask[index]) continue;
      const pixel = index * 4;
      output[pixel] = sourcePixels[pixel];
      output[pixel + 1] = sourcePixels[pixel + 1];
      output[pixel + 2] = sourcePixels[pixel + 2];
      output[pixel + 3] = sourcePixels[pixel + 3];

      // O preenchimento amostrado mantém a massa de cabelo contínua quando a mecha se move.
      const x = index % width;
      const y = Math.floor(index / width);
      let fillPixel = -1;
      for (let distance = 3; distance <= 22; distance += 1) {
        const innerX = x + direction * distance;
        if (innerX < 0 || innerX >= width) break;
        const candidate = (y * width + innerX) * 4;
        if (isRedHair(candidate)) {
          fillPixel = candidate;
          break;
        }
      }
      if (fillPixel >= 0 && sourcePixels[pixel + 3] > 22) {
        bodyPixels[pixel] = sourcePixels[fillPixel];
        bodyPixels[pixel + 1] = sourcePixels[fillPixel + 1];
        bodyPixels[pixel + 2] = sourcePixels[fillPixel + 2];
        bodyPixels[pixel + 3] = sourcePixels[pixel + 3];
      } else {
        bodyPixels[pixel] = 0;
        bodyPixels[pixel + 1] = 0;
        bodyPixels[pixel + 2] = 0;
        bodyPixels[pixel + 3] = 0;
      }
    }
  };

  split(leftMask, leftPixels, 1);
  split(rightMask, rightPixels, -1);

  return {
    body: canvasFromPixels(width, height, bodyPixels),
    leftHair: canvasFromPixels(width, height, leftPixels),
    rightHair: canvasFromPixels(width, height, rightPixels),
  };
}

function createMesh(texture: THREE.Texture, order: number, segments: number) {
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = true;

  const material = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    alphaTest: 0.008,
    depthWrite: false,
    toneMapped: false,
  });
  const geometry = new THREE.PlaneGeometry(imageAspect, 1, segments, segments * 2);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.renderOrder = order;
  return mesh;
}

function makeHairMesh(mesh: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial>, side: "left" | "right", phase: number): HairMesh {
  const positions = mesh.geometry.attributes.position.array as Float32Array;
  return { mesh, basePositions: positions.slice(), side, phase };
}

function animateHair(layer: HairMesh, time: number, motion: number, speed: number) {
  const position = layer.mesh.geometry.attributes.position as THREE.BufferAttribute;
  const uv = layer.mesh.geometry.attributes.uv as THREE.BufferAttribute;
  const sideDirection = layer.side === "left" ? -1 : 1;
  const phaseTime = time * speed;

  for (let index = 0; index < position.count; index += 1) {
    const u = uv.getX(index);
    const v = uv.getY(index);
    const sideWeight = layer.side === "left"
      ? 1 - smoothstep(0.16, 0.38, u)
      : smoothstep(0.62, 0.84, u);
    const tipWeight = 1 - smoothstep(0.22, 0.78, v);
    const weight = sideWeight * tipWeight;
    const wave = Math.sin(phaseTime * 1.2 - v * 3 + layer.phase);
    const secondaryWave = Math.sin(phaseTime * 0.72 - v * 1.8 + layer.phase * 0.6);
    const base = index * 3;

    position.setX(index, layer.basePositions[base] + sideDirection * (wave + secondaryWave * 0.18) * 0.011 * motion * weight);
    position.setY(index, layer.basePositions[base + 1] + Math.cos(phaseTime * 0.88 - v * 2.2 + layer.phase) * 0.0035 * motion * weight);
  }
  position.needsUpdate = true;
}

export default function StartupMascot({ src, className, onLoad, onError, motionScale = 1, speed = 1 }: StartupMascotProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const motionScaleRef = useRef(motionScale);
  const speedRef = useRef(speed);
  const onLoadRef = useRef(onLoad);
  const onErrorRef = useRef(onError);
  const [threeReady, setThreeReady] = useState(false);
  motionScaleRef.current = motionScale;
  speedRef.current = speed;
  onLoadRef.current = onLoad;
  onErrorRef.current = onError;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let disposed = false;
    let renderer: THREE.WebGLRenderer | undefined;
    let resizeObserver: ResizeObserver | undefined;
    let loadedTexture: THREE.Texture | undefined;
    let layerTextures: THREE.CanvasTexture[] = [];
    let meshes: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial>[] = [];
    let hairMeshes: HairMesh[] = [];
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");

    const setup = async () => {
      try {
        loadedTexture = await new THREE.TextureLoader().loadAsync(sourcePath);
        if (disposed) {
          loadedTexture.dispose();
          return;
        }
        const source = loadedTexture.image as HTMLImageElement;
        const pixelLayers = createPixelLayers(source);
        layerTextures = [pixelLayers.body, pixelLayers.leftHair, pixelLayers.rightHair].map((canvasLayer) => new THREE.CanvasTexture(canvasLayer));
        loadedTexture.dispose();
        loadedTexture = undefined;

        renderer = new THREE.WebGLRenderer({
          canvas,
          alpha: true,
          antialias: true,
          powerPreference: "low-power",
          premultipliedAlpha: true,
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.setClearColor(0x000000, 0);

        const scene = new THREE.Scene();
        const camera = new THREE.OrthographicCamera(-0.5, 0.5, 0.5, -0.5, 0.01, 10);
        camera.position.z = 2;

        const body = createMesh(layerTextures[0], 1, 1);
        const left = createMesh(layerTextures[1], 2, 34);
        const right = createMesh(layerTextures[2], 3, 34);
        scene.add(body, left, right);
        meshes = [body, left, right];
        hairMeshes = [makeHairMesh(left, "left", 0), makeHairMesh(right, "right", 0.42)];

        const resize = () => {
          if (!renderer || disposed) return;
          const rect = canvas.getBoundingClientRect();
          const width = Math.max(1, rect.width);
          const height = Math.max(1, rect.height);
          const viewAspect = width / height;
          const fit = Math.min(1, viewAspect / imageAspect);
          meshes.forEach((mesh) => mesh.scale.set(fit, fit, 1));
          camera.left = -viewAspect / 2;
          camera.right = viewAspect / 2;
          camera.top = 0.5;
          camera.bottom = -0.5;
          camera.updateProjectionMatrix();
          renderer.setSize(width, height, false);
        };

        resizeObserver = new ResizeObserver(resize);
        resizeObserver.observe(canvas);
        resize();

        renderer.setAnimationLoop((now) => {
          if (disposed || !renderer) return;
          const time = now / 1000;
          const motion = motionScaleRef.current * (reducedMotion?.matches ? 0.38 : 1);
          hairMeshes.forEach((layer) => animateHair(layer, time, motion, speedRef.current));
          renderer.render(scene, camera);
        });
        if (!disposed) {
          setThreeReady(true);
          onLoadRef.current();
        }
      } catch {
        if (!disposed) onErrorRef.current();
      }
    };

    void setup();
    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      if (renderer) {
        renderer.setAnimationLoop(null);
        renderer.dispose();
      }
      meshes.forEach(({ geometry, material }) => {
        geometry.dispose();
        material.dispose();
      });
      layerTextures.forEach((texture) => texture.dispose());
      loadedTexture?.dispose();
    };
  }, []);

  return (
    <div className={`${className}${threeReady ? " startup-splash-mascot-three-ready" : ""}`}>
      <img src={src} alt="" aria-hidden="true" className="startup-splash-mascot-image" loading="eager" decoding="sync" />
      <canvas ref={canvasRef} className="startup-splash-mascot-canvas" aria-hidden="true" />
    </div>
  );
}
