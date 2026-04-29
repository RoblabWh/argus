import {
  Component,
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import {
  OrbitControls,
  FlyControls,
  Bounds,
  Html,
  Line,
  GizmoHelper,
  GizmoViewport,
  Sky,
} from "@react-three/drei";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";
import { BufferAttribute, Vector3 } from "three";
import type { BufferGeometry } from "three";
import {
  AlertTriangle,
  ArrowLeftRight,
  ChevronDown,
  ChevronRight,
  Loader2,
  PanelLeftClose,
  RotateCcw,
  Settings2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import type { Keyframe } from "@/types/reconstruction";

/* -------------------------------------------------------------------------- */
/* Error boundary                                                             */
/* -------------------------------------------------------------------------- */

interface CanvasErrorBoundaryProps {
  children: ReactNode;
  resetKey: string | number;
  onRetry: () => void;
}

interface CanvasErrorBoundaryState {
  error: Error | null;
}

class CanvasErrorBoundary extends Component<CanvasErrorBoundaryProps, CanvasErrorBoundaryState> {
  state: CanvasErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): CanvasErrorBoundaryState {
    return { error };
  }

  componentDidUpdate(prev: CanvasErrorBoundaryProps) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="w-full h-full flex flex-col items-center justify-center gap-3 text-muted-foreground p-6 text-center">
          <AlertTriangle className="w-10 h-10 text-destructive" />
          <div>
            <p className="text-sm font-medium text-foreground">Failed to load point cloud</p>
            <p className="text-xs mt-1 max-w-md break-words">{this.state.error.message}</p>
          </div>
          <Button
            size="sm"
            onClick={() => {
              this.setState({ error: null });
              this.props.onRetry();
            }}
          >
            Retry
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}

/* -------------------------------------------------------------------------- */
/* Constants & helpers                                                        */
/* -------------------------------------------------------------------------- */

const DEFAULT_POINT_SIZE = 2;
const MIN_POINT_SIZE = 1;
const MAX_POINT_SIZE = 6;

const DEFAULT_SPHERE_SIZE = 0.035;
const MIN_SPHERE_SIZE = 0.0001;
const MAX_SPHERE_SIZE = 0.02;
const HIGHLIGHT_SCALE = 1.5;

const DEFAULT_CLOUD_SCALE = 1;
const MIN_CLOUD_SCALE = 0.1;
const MAX_CLOUD_SCALE = 10;

type CloudKind = "sparse" | "dense";
type ColorMode = "single" | "axis-gradient" | "vertex";
type GradientAxis = "x" | "y" | "z";
type GradientInterpolation = "linear" | "hsv" | "oklab";
type NavMode = "orbit" | "fly" | "walk";

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toFixed(2).padStart(5, "0")}`;
}

function parseHex(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  return [r, g, b];
}

// ~6 ops. Returns [0..1, 0..1, 0..1]
function rgbToHsv(r: number, g: number, b: number): [number, number, number] {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  const s = max === 0 ? 0 : d / max;
  const v = max;
  let h = 0;
  if (d > 0) {
    if      (max === r) h = ((g - b) / d + 6) % 6;
    else if (max === g) h =  (b - r) / d + 2;
    else                h =  (r - g) / d + 4;
    h *= 60;
  }
  return [h, s, v]; // h in [0, 360), s/v in [0, 1]
}

// ~8 ops. Input h in [0, 360), s/v in [0, 1]. Returns [0..1, 0..1, 0..1]
function hsvToRgb(h: number, s: number, v: number): [number, number, number] {
  h = ((h % 360) + 360) % 360; // safe wrap
  const i = Math.floor(h / 60);
  const f = h / 60 - i;
  const p = v * (1 - s);
  const q = v * (1 - f * s);
  const t = v * (1 - (1 - f) * s);
  switch (i) {
    case 0: return [v, t, p];
    case 1: return [q, v, p];
    case 2: return [p, v, t];
    case 3: return [p, q, v];
    case 4: return [t, p, v];
    default: return [v, p, q];
  }
}

function lin(x: number): number {
  return x > 0.04045 ? ((x + 0.055) / 1.055) ** 2.4 : x / 12.92;
}
function gam(x: number): number {
  return x > 0.0031308 ? 1.055 * x ** (1 / 2.4) - 0.055 : 12.92 * x;
}

// sRGB [0..1] → Oklab [L ~0..1, a/b ~-0.5..0.5]
function rgbToOklab(r: number, g: number, b: number): [number, number, number] {
  const rl = lin(r), gl = lin(g), bl = lin(b);
  const l = Math.cbrt(0.4122214708 * rl + 0.5363325363 * gl + 0.0514459929 * bl);
  const m = Math.cbrt(0.2119034982 * rl + 0.6806995451 * gl + 0.1073969566 * bl);
  const s = Math.cbrt(0.0883024619 * rl + 0.2817188376 * gl + 0.6299787005 * bl);
  return [
     0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
     1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
     0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
  ];
}

// Oklab → sRGB [0..1], clamped
function oklabToRgb(L: number, a: number, b: number): [number, number, number] {
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.2914855480 * b;
  const l = l_ * l_ * l_;
  const m = m_ * m_ * m_;
  const s = s_ * s_ * s_;
  return [
    Math.max(0, Math.min(1, gam(+4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s))),
    Math.max(0, Math.min(1, gam(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s))),
    Math.max(0, Math.min(1, gam(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s))),
  ];
}

function buildGradientColors(
  positions: Float32Array,
  axis: 0 | 1 | 2,
  startHex: string,
  endHex: string,
  loFrac: number,
  hiFrac: number,
  interpolation: GradientInterpolation,
): Float32Array {
  const [sR, sG, sB] = parseHex(startHex);
  const [eR, eG, eB] = parseHex(endHex);
  const count = positions.length / 3;

  let min = Infinity;
  let max = -Infinity;
  for (let i = 0; i < count; i++) {
    const v = positions[i * 3 + axis];
    if (v < min) min = v;
    if (v > max) max = v;
  }
  const fullRange = max - min || 1;
  const loV = min + loFrac * fullRange;
  const hiV = min + hiFrac * fullRange;
  const window = hiV - loV || 1;

  // Pre-compute per-mode constants.
  const [h1, s1, v1] = rgbToHsv(sR, sG, sB);
  const [h2, s2, v2] = rgbToHsv(eR, eG, eB);
  let dh = h2 - h1;
  if (dh > 180) dh -= 360;
  if (dh < -180) dh += 360;

  const [L1, oa1, ob1] = rgbToOklab(sR, sG, sB);
  const [L2, oa2, ob2] = rgbToOklab(eR, eG, eB);

  const colors = new Float32Array(positions.length);
  for (let i = 0; i < count; i++) {
    let t = (positions[i * 3 + axis] - loV) / window;
    if (t < 0) t = 0;
    else if (t > 1) t = 1;

    let r: number, g: number, b: number;
    if (interpolation === "linear") {
      r = sR + (eR - sR) * t;
      g = sG + (eG - sG) * t;
      b = sB + (eB - sB) * t;
    } else if (interpolation === "hsv") {
      [r, g, b] = hsvToRgb(h1 + dh * t, s1 + (s2 - s1) * t, v1 + (v2 - v1) * t);
    } else {
      [r, g, b] = oklabToRgb(
        L1 + (L2 - L1) * t,
        oa1 + (oa2 - oa1) * t,
        ob1 + (ob2 - ob1) * t,
      );
    }
    colors[i * 3 + 0] = r;
    colors[i * 3 + 1] = g;
    colors[i * 3 + 2] = b;
  }
  return colors;
}

const AXIS_INDEX: Record<GradientAxis, 0 | 1 | 2> = { x: 0, y: 1, z: 2 };

/* -------------------------------------------------------------------------- */
/* Walk controls — drag to look + WASD/RF translate                            */
/* -------------------------------------------------------------------------- */

interface WalkControlsProps {
  enabled: boolean;
  moveSpeed?: number;
  sensitivity?: number;
  rollSpeed?: number;
}

function WalkControls({
  enabled,
  moveSpeed = 2,
  sensitivity = 0.003,
  rollSpeed = 1,
}: WalkControlsProps) {
  const { camera, gl, invalidate } = useThree();
  const dragging = useRef(false);
  const lastMouse = useRef<{ x: number; y: number } | null>(null);
  const keys = useRef({
    w: false, a: false, s: false, d: false,
    r: false, f: false, q: false, e: false,
  });

  useEffect(() => {
    if (!enabled) return;
    const dom = gl.domElement;
    dom.style.cursor = "grab";
    camera.rotation.order = "YXZ";
    // Auto-level horizon when entering walk mode (Fly mode can leave roll behind).
    camera.rotation.z = 0;
    camera.near = 0.001;
    invalidate();

    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      dragging.current = true;
      lastMouse.current = { x: e.clientX, y: e.clientY };
      dom.style.cursor = "grabbing";
      dom.setPointerCapture?.(e.pointerId);
    };
    const onPointerMove = (e: PointerEvent) => {
      if (!dragging.current || !lastMouse.current) return;
      const dx = e.clientX - lastMouse.current.x;
      const dy = e.clientY - lastMouse.current.y;
      lastMouse.current = { x: e.clientX, y: e.clientY };
      camera.rotation.y -= dx * sensitivity;
      camera.rotation.x -= dy * sensitivity;
      const limit = Math.PI / 2 - 0.001;
      if (camera.rotation.x > limit) camera.rotation.x = limit;
      else if (camera.rotation.x < -limit) camera.rotation.x = -limit;
      invalidate();
    };
    const endDrag = (e: PointerEvent) => {
      if (!dragging.current) return;
      dragging.current = false;
      lastMouse.current = null;
      dom.style.cursor = "grab";
      try { dom.releasePointerCapture?.(e.pointerId); } catch { /* ignore */ }
    };

    const setKey = (e: KeyboardEvent, value: boolean) => {
      const tag = (document.activeElement as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const k = e.key.toLowerCase();
      if (k in keys.current) {
        (keys.current as Record<string, boolean>)[k] = value;
      }
    };
    const onKeyDown = (e: KeyboardEvent) => setKey(e, true);
    const onKeyUp = (e: KeyboardEvent) => setKey(e, false);

    dom.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", endDrag);
    window.addEventListener("pointercancel", endDrag);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);

    return () => {
      dom.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", endDrag);
      window.removeEventListener("pointercancel", endDrag);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      dom.style.cursor = "";
      dragging.current = false;
      lastMouse.current = null;
      keys.current = {
        w: false, a: false, s: false, d: false,
        r: false, f: false, q: false, e: false,
      };
    };
  }, [enabled, camera, gl, sensitivity, invalidate]);

  const fwd = useRef(new Vector3());
  const right = useRef(new Vector3());
  const worldUp = useRef(new Vector3(0, 1, 0));

  useFrame((_, dt) => {
    if (!enabled) return;
    const k = keys.current;
    if (!k.w && !k.a && !k.s && !k.d && !k.r && !k.f && !k.q && !k.e) return;
    const speed = moveSpeed * dt;
    camera.getWorldDirection(fwd.current);
    right.current.crossVectors(fwd.current, camera.up).normalize();
    if (k.w) camera.position.addScaledVector(fwd.current, speed);
    if (k.s) camera.position.addScaledVector(fwd.current, -speed);
    if (k.d) camera.position.addScaledVector(right.current, speed);
    if (k.a) camera.position.addScaledVector(right.current, -speed);
    if (k.r) camera.position.addScaledVector(worldUp.current, speed);
    if (k.f) camera.position.addScaledVector(worldUp.current, -speed);
    if (k.q) camera.rotation.z += rollSpeed * dt;
    if (k.e) camera.rotation.z -= rollSpeed * dt;
    invalidate();
  });

  return null;
}

/* -------------------------------------------------------------------------- */
/* Point cloud                                                                */
/* -------------------------------------------------------------------------- */

interface PointCloudProps {
  url: string;
  pointSize: number;
  colorMode: ColorMode;
  singleColor: string;
  gradientAxis: GradientAxis;
  gradientStart: string;
  gradientEnd: string;
  gradientRange: [number, number];
  gradientInterpolation: GradientInterpolation;
  onHasColorChange?: (hasColor: boolean) => void;
}

function PointCloud({
  url,
  pointSize,
  colorMode,
  singleColor,
  gradientAxis,
  gradientStart,
  gradientEnd,
  gradientRange,
  gradientInterpolation,
  onHasColorChange,
}: PointCloudProps) {
  const geometry = useLoader(PLYLoader, url) as BufferGeometry;
  const hasVertexColor = !!geometry.attributes.color;

  useEffect(() => {
    onHasColorChange?.(hasVertexColor);
  }, [hasVertexColor, onHasColorChange]);

  // Build the geometry actually rendered. We clone so we don't mutate the
  // loader-cached original. For "single" mode we strip any leftover color
  // attribute so the shader can't pick it up under a stale program variant.
  const renderGeometry = useMemo(() => {
    if (colorMode === "axis-gradient") {
      const positions = geometry.attributes.position?.array as Float32Array | undefined;
      if (!positions) return geometry;
      const cloned = geometry.clone();
      const colors = buildGradientColors(
        positions,
        AXIS_INDEX[gradientAxis],
        gradientStart,
        gradientEnd,
        gradientRange[0] / 100,
        gradientRange[1] / 100,
        gradientInterpolation,
      );
      cloned.setAttribute("color", new BufferAttribute(colors, 3));
      return cloned;
    }
    if (colorMode === "single" && hasVertexColor) {
      const cloned = geometry.clone();
      cloned.deleteAttribute("color");
      return cloned;
    }
    return geometry;
  }, [
    geometry,
    hasVertexColor,
    colorMode,
    gradientAxis,
    gradientStart,
    gradientEnd,
    gradientRange,
    gradientInterpolation,
  ]);

  const useVertexColors =
    colorMode === "vertex" ? hasVertexColor : colorMode === "axis-gradient";

  return (
    <points geometry={renderGeometry}>
      {/* key forces material remount so the USE_COLOR shader define is freshly
          compiled for each mode — sidesteps three.js's program cache.
          When vertexColors=true, color must be white (multiplicative identity). */}
      <pointsMaterial
        key={colorMode}
        size={pointSize}
        sizeAttenuation={false}
        vertexColors={useVertexColors}
        color={useVertexColors ? "#ffffff" : singleColor}
      />
    </points>
  );
}

/* -------------------------------------------------------------------------- */
/* Trajectory                                                                  */
/* -------------------------------------------------------------------------- */

interface TrajectoryProps {
  keyframes: Keyframe[];
}

function Trajectory({ keyframes }: TrajectoryProps) {
  const points = useMemo(
    () =>
      keyframes
        .filter((kf) => kf.tx != null && kf.ty != null && kf.tz != null)
        .map((kf) => [kf.tx!, kf.ty!, kf.tz!] as [number, number, number]),
    [keyframes],
  );

  if (points.length < 2) return null;

  return <Line points={points} color="#facc15" lineWidth={2} />;
}

/* -------------------------------------------------------------------------- */
/* Keyframe markers                                                            */
/* -------------------------------------------------------------------------- */

interface KeyframeMarkersProps {
  keyframes: Keyframe[];
  highlightedIndex: number | null;
  onSelect: (idx: number) => void;
  sphereSize: number;
}

function KeyframeMarkers({ keyframes, highlightedIndex, onSelect, sphereSize }: KeyframeMarkersProps) {
  return (
    <>
      {keyframes.map((kf, idx) => {
        if (kf.tx == null || kf.ty == null || kf.tz == null) return null;
        const isHighlighted = highlightedIndex === idx;
        return (
          <mesh
            key={idx}
            position={[kf.tx, kf.ty, kf.tz]}
            scale={isHighlighted ? HIGHLIGHT_SCALE : 1}
            onClick={(e) => {
              e.stopPropagation();
              onSelect(idx);
            }}
            onPointerOver={(e) => {
              e.stopPropagation();
              document.body.style.cursor = "pointer";
            }}
            onPointerOut={() => {
              document.body.style.cursor = "auto";
            }}
          >
            <sphereGeometry args={[sphereSize, 12, 12]} />
            <meshStandardMaterial
              color={isHighlighted ? "#ffffff" : "#22d3ee"}
              emissive={isHighlighted ? "#ffffff" : "#000000"}
              emissiveIntensity={isHighlighted ? 0.6 : 0}
            />
          </mesh>
        );
      })}
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Popup                                                                       */
/* -------------------------------------------------------------------------- */

interface KeyframePopupProps {
  keyframe: Keyframe;
  index: number;
  total: number;
  onOpenViewer: (idx: number) => void;
  onClose: () => void;
}

function KeyframePopup({ keyframe, index, total, onOpenViewer, onClose }: KeyframePopupProps) {
  if (keyframe.tx == null || keyframe.ty == null || keyframe.tz == null) return null;

  const stop = (e: React.SyntheticEvent) => {
    e.stopPropagation();
  };

  return (
    <Html
      position={[keyframe.tx, keyframe.ty, keyframe.tz]}
      center
      zIndexRange={[100, 0]}
    >
      <Card
        className="p-3 min-w-[180px] shadow-lg"
        onClick={stop}
        onPointerDown={stop}
        onPointerUp={stop}
      >
        <div className="text-sm font-medium">
          Keyframe {index + 1} / {total}
        </div>
        <div className="text-xs text-muted-foreground mt-1">
          {formatTimestamp(keyframe.timestamp)}
        </div>
        <div className="flex gap-2 mt-3">
          <Button size="sm" onClick={() => onOpenViewer(index)}>
            Open in Viewer
          </Button>
          <Button size="sm" variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </Card>
    </Html>
  );
}

/* -------------------------------------------------------------------------- */
/* Main tab                                                                    */
/* -------------------------------------------------------------------------- */

interface Props {
  results: {
    sparse_pointcloud_url: string | null;
    dense_pointcloud_url: string | null;
    has_dense_pointcloud: boolean;
  };
  keyframes: Keyframe[];
  apiUrl: string;
  onOpenViewer: (idx: number) => void;
}

export function ReconstructionPointcloudTab({
  results,
  keyframes,
  apiUrl,
  onOpenViewer,
}: Props) {
  const sparseUrl = results.sparse_pointcloud_url
    ? `${apiUrl}${results.sparse_pointcloud_url}`
    : null;
  const denseUrl = results.dense_pointcloud_url
    ? `${apiUrl}${results.dense_pointcloud_url}`
    : null;

  const [cloudKind, setCloudKind] = useState<CloudKind>(sparseUrl ? "sparse" : "dense");
  const [pointSize, setPointSize] = useState(DEFAULT_POINT_SIZE);
  const [sphereSize, setSphereSize] = useState(DEFAULT_SPHERE_SIZE);
  const [cloudScale, setCloudScale] = useState(DEFAULT_CLOUD_SCALE);
  const [highlightedIndex, setHighlightedIndex] = useState<number | null>(null);
  const [retryCounter, setRetryCounter] = useState(0);
  const [toolbarOpen, setToolbarOpen] = useState(true);

  // Overlays
  const [showTrajectory, setShowTrajectory] = useState(true);
  const [showKeyframeMarkers, setShowKeyframeMarkers] = useState(true);
  const [showAxes, setShowAxes] = useState(false);

  // Coloring state
  const [hasVertexColor, setHasVertexColor] = useState(false);
  const [colorMode, setColorMode] = useState<ColorMode>("axis-gradient");
  const [singleColor, setSingleColor] = useState("#8ab4f8");
  const [gradientAxis, setGradientAxis] = useState<GradientAxis>("z");
  const [gradientStart, setGradientStart] = useState("#0059ff");
  const [gradientEnd, setGradientEnd] = useState("#ffa600");
  const [gradientRange, setGradientRange] = useState<[number, number]>([0, 100]);
  const [gradientInterpolation, setGradientInterpolation] =
    useState<GradientInterpolation>("hsv");
  const [rangeOpen, setRangeOpen] = useState(false);
  const [skyBackground, setSkyBackground] = useState(false);

  // Navigation
  const [navMode, setNavMode] = useState<NavMode>("orbit");

  // Default to vertex colors when a cloud with color attribute loads.
  useEffect(() => {
    if (hasVertexColor) setColorMode((m) => (m === "axis-gradient" ? "vertex" : m));
  }, [hasVertexColor]);

  // Close any open popup when keyframe markers are hidden.
  useEffect(() => {
    if (!showKeyframeMarkers) setHighlightedIndex(null);
  }, [showKeyframeMarkers]);

  // Keep cloud-kind sane if URLs change.
  useEffect(() => {
    if (cloudKind === "sparse" && !sparseUrl && denseUrl) setCloudKind("dense");
    if (cloudKind === "dense" && !denseUrl && sparseUrl) setCloudKind("sparse");
  }, [cloudKind, sparseUrl, denseUrl]);

  const activeUrl = cloudKind === "dense" ? denseUrl : sparseUrl;

  if (!activeUrl) {
    return (
      <div className="w-full h-full flex items-center justify-center text-muted-foreground text-sm">
        No point cloud available.
      </div>
    );
  }

  const highlightedKeyframe =
    highlightedIndex != null ? keyframes[highlightedIndex] : null;

  const cloudKey = `${activeUrl}#${retryCounter}`;

  const navHelp =
    navMode === "fly"
      ? "Drag to look · WASD move · RF up/down"
      : navMode === "walk"
      ? "Hold left + drag to look · WASD move · QE roll"
      : "Drag to orbit · scroll zoom · right-drag pan";

  return (
    <div className="relative w-full h-full">
      <CanvasErrorBoundary
        resetKey={cloudKey}
        onRetry={() => setRetryCounter((c) => c + 1)}
      >
        <Canvas
          frameloop={navMode === "orbit" ? "demand" : "always"}
          camera={{ fov: 60, near: 0.0001, far: 500, position: [0, 0, 5] }}
          gl={{ antialias: true }}
          onPointerMissed={() => setHighlightedIndex(null)}
        >
          <ambientLight intensity={0.8} />
          <directionalLight position={[5, 10, 5]} intensity={0.6} />
          {skyBackground && <Sky distance={450000} sunPosition={[0, 1, 1]} inclination={0} turbidity={0.5} mieCoefficient={0.005} mieDirectionalG={0.85}/>}
          <Suspense
            fallback={
              <Html center>
                <div className="flex items-center gap-2 text-white text-sm bg-black/60 px-3 py-2 rounded-md backdrop-blur-sm">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Loading point cloud…
                </div>
              </Html>
            }
          >
            {/* Flip OpenCV/TUM (+Y down, +Z forward) into Three's +Y up; cloudScale scales the whole scene. */}
            <group rotation={[Math.PI, 0, 0]} scale={cloudScale}>
              <Bounds fit clip margin={1.2}>
                <PointCloud
                  key={cloudKey}
                  url={activeUrl}
                  pointSize={pointSize}
                  colorMode={colorMode}
                  singleColor={singleColor}
                  gradientAxis={gradientAxis}
                  gradientStart={gradientStart}
                  gradientEnd={gradientEnd}
                  gradientRange={gradientRange}
                  gradientInterpolation={gradientInterpolation}
                  onHasColorChange={setHasVertexColor}
                />
              </Bounds>
              {showTrajectory && <Trajectory keyframes={keyframes} />}
              {showKeyframeMarkers && (
                <KeyframeMarkers
                  keyframes={keyframes}
                  highlightedIndex={highlightedIndex}
                  onSelect={setHighlightedIndex}
                  sphereSize={sphereSize}
                />
              )}
              {showKeyframeMarkers &&
                highlightedKeyframe &&
                highlightedIndex != null && (
                  <KeyframePopup
                    keyframe={highlightedKeyframe}
                    index={highlightedIndex}
                    total={keyframes.length}
                    onOpenViewer={onOpenViewer}
                    onClose={() => setHighlightedIndex(null)}
                  />
                )}
              {showAxes && <axesHelper args={[1]} />}
            </group>
          </Suspense>

          {/* Controls — only one mounted at a time so they don't fight */}
          {navMode === "orbit" && <OrbitControls makeDefault />}
          {navMode === "fly" && (
            <FlyControls makeDefault movementSpeed={2} rollSpeed={0.5} dragToLook />
          )}
          {navMode === "walk" && <WalkControls enabled moveSpeed={2} sensitivity={0.003} />}

          {/* Corner orientation widget — outside the rotated group so it shows world axes */}
          {showAxes && (
            <GizmoHelper alignment="bottom-right" margin={[80, 80]}>
              <GizmoViewport
                axisColors={["#ef4444", "#22c55e", "#3b82f6"]}
                labelColor="white"
              />
            </GizmoHelper>
          )}
        </Canvas>
      </CanvasErrorBoundary>

      {/* Toolbar overlay — collapsible */}
      {!toolbarOpen ? (
        <Button
          size="icon"
          variant="secondary"
          className="absolute top-2 left-2 z-10 h-9 w-9 shadow-lg bg-background/85 backdrop-blur-sm"
          onClick={() => setToolbarOpen(true)}
          title="Show settings"
        >
          <Settings2 className="w-4 h-4" />
        </Button>
      ) : (
        <Card className="absolute top-2 left-2 p-3 flex flex-col gap-3 bg-background/85 backdrop-blur-sm shadow-lg z-10 min-w-[230px] max-h-[calc(100%-1rem)] overflow-auto">
          <div className="flex items-center justify-between -mb-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Settings
            </span>
            <Button
              size="icon"
              variant="ghost"
              className="h-6 w-6"
              onClick={() => setToolbarOpen(false)}
              title="Hide settings"
            >
              <PanelLeftClose className="w-4 h-4" />
            </Button>
          </div>

          {/* Cloud — always visible (small, frequently used) */}
          {results.has_dense_pointcloud && denseUrl && sparseUrl && (
            <>
              <Separator />
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">Cloud</span>
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant={cloudKind === "sparse" ? "default" : "outline"}
                    onClick={() => setCloudKind("sparse")}
                    className="flex-1"
                  >
                    Sparse
                  </Button>
                  <Button
                    size="sm"
                    variant={cloudKind === "dense" ? "default" : "outline"}
                    onClick={() => setCloudKind("dense")}
                    className="flex-1"
                  >
                    Dense
                  </Button>
                </div>
              </div>
            </>
          )}

          <Accordion
            type="multiple"
            defaultValue={["appearance"]}
            className="-mx-1"
          >
            {/* Display */}
            <AccordionItem value="appearance">
              <AccordionTrigger className="py-2 px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Appearance
              </AccordionTrigger>
              <AccordionContent className="pt-1 pb-2 px-1 flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">Point size</span>
                    <span className="text-xs tabular-nums text-muted-foreground">
                      {pointSize.toFixed(1)}
                    </span>
                  </div>
                  <Slider
                    value={[pointSize]}
                    min={MIN_POINT_SIZE}
                    max={MAX_POINT_SIZE}
                    step={0.5}
                    onValueChange={(v) => setPointSize(v[0])}
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">Cloud scale</span>
                    <div className="flex items-center gap-1">
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {cloudScale.toFixed(1)}×
                      </span>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-5 w-5"
                        onClick={() => setCloudScale(DEFAULT_CLOUD_SCALE)}
                        title="Reset to 1×"
                      >
                        <RotateCcw className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                  <Slider
                    value={[cloudScale]}
                    min={MIN_CLOUD_SCALE}
                    max={MAX_CLOUD_SCALE}
                    step={0.1}
                    onValueChange={(v) => setCloudScale(v[0])}
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-muted-foreground">Color</span>

                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant={colorMode === "single" ? "default" : "outline"}
                      onClick={() => setColorMode("single")}
                      className="flex-1 px-2"
                    >
                      Single
                    </Button>
                    <Button
                      size="sm"
                      variant={colorMode === "axis-gradient" ? "default" : "outline"}
                      onClick={() => setColorMode("axis-gradient")}
                      className="flex-1 px-2"
                    >
                      Gradient
                    </Button>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="sm"
                            variant={colorMode === "vertex" ? "default" : "outline"}
                            onClick={() => setColorMode("vertex")}
                            className="flex-1 px-2"
                            disabled={!hasVertexColor}
                            title={hasVertexColor ? "Use baked vertex colors" : "Cloud has no color data"}
                          >
                            Vertex
                          </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="text-xs">{hasVertexColor ? "Use baked vertex colors" : "Sparse pointclouds have no vertex color data"}.</p>
                      </TooltipContent>
                    </Tooltip>
                    </TooltipProvider>
                  </div>

                  {colorMode === "single" && (
                    <label className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
                      Color
                      <input
                        type="color"
                        value={singleColor}
                        onChange={(e) => setSingleColor(e.target.value)}
                        className="h-7 w-10 rounded cursor-pointer border border-border bg-transparent"
                      />
                    </label>
                  )}

                  {colorMode === "axis-gradient" && (
                    <div className="flex flex-col gap-1.5 mt-1">
                      <div className="flex gap-1">
                        {(["x", "y", "z"] as GradientAxis[]).map((ax) => (
                          <Button
                            key={ax}
                            size="sm"
                            variant={gradientAxis === ax ? "default" : "outline"}
                            onClick={() => setGradientAxis(ax)}
                            className="flex-1 px-0"
                          >
                            {ax.toUpperCase()}
                          </Button>
                        ))}
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          value={gradientStart}
                          onChange={(e) => setGradientStart(e.target.value)}
                          className="h-7 w-10 rounded cursor-pointer border border-border bg-transparent"
                        />
                        <Button
                          size="sm"
                          variant="ghost"
                          className="px-1.5 h-7"
                          onClick={() => {
                            setGradientStart(gradientEnd);
                            setGradientEnd(gradientStart);
                          }}
                          title="Swap colors"
                        >
                          <ArrowLeftRight className="w-3.5 h-3.5" />
                        </Button>
                        <input
                          type="color"
                          value={gradientEnd}
                          onChange={(e) => setGradientEnd(e.target.value)}
                          className="h-7 w-10 rounded cursor-pointer border border-border bg-transparent"
                        />
                        <Select
                          value={gradientInterpolation}
                          onValueChange={(v) =>
                            setGradientInterpolation(v as GradientInterpolation)
                          }
                        >
                          <SelectTrigger
                            className="h-7 flex-1 text-xs px-2"
                            title="Interpolation mode"
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="linear">Linear</SelectItem>
                            <SelectItem value="hsv">HSV</SelectItem>
                            <SelectItem value="oklab">OKLab</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Range disclosure */}
                      <button
                        type="button"
                        onClick={() => setRangeOpen((o) => !o)}
                        className="mt-1 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {rangeOpen ? (
                          <ChevronDown className="w-3 h-3" />
                        ) : (
                          <ChevronRight className="w-3 h-3" />
                        )}
                        Range
                      </button>
                      {rangeOpen && (
                        <div className="flex flex-col gap-1.5">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] tabular-nums text-muted-foreground">
                              {gradientRange[0]}% – {gradientRange[1]}%
                            </span>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-5 w-5"
                              onClick={() => setGradientRange([0, 100])}
                              title="Reset range"
                            >
                              <RotateCcw className="w-3 h-3" />
                            </Button>
                          </div>
                          <Slider
                            value={gradientRange}
                            min={0}
                            max={100}
                            step={1}
                            minStepsBetweenThumbs={1}
                            onValueChange={(v) =>
                              setGradientRange([v[0], v[1]] as [number, number])
                            }
                          />
                          <p className="text-[10px] leading-tight text-muted-foreground">
                            Reposition the gradient's start/ end.
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                  <div className="pt-1 pb-2 px-1 flex flex-col gap-2">
                    <label className="flex items-center justify-between gap-2 text-xs font-medium text-muted-foreground">
                      Sky background
                      <Switch checked={skyBackground} onCheckedChange={setSkyBackground} />
                    </label>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Navigation */}
            <AccordionItem value="navigation">
              <AccordionTrigger className="py-2 px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Navigation
              </AccordionTrigger>
              <AccordionContent className="pt-1 pb-2 px-1 flex flex-col gap-1.5">
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant={navMode === "orbit" ? "default" : "outline"}
                    onClick={() => setNavMode("orbit")}
                    className="flex-1 px-2"
                  >
                    Orbit
                  </Button>
                  <Button
                    size="sm"
                    variant={navMode === "fly" ? "default" : "outline"}
                    onClick={() => setNavMode("fly")}
                    className="flex-1 px-2"
                  >
                    Fly
                  </Button>
                  <Button
                    size="sm"
                    variant={navMode === "walk" ? "default" : "outline"}
                    onClick={() => setNavMode("walk")}
                    className="flex-1 px-2"
                  >
                    Walk
                  </Button>
                </div>
                <p className="text-[10px] leading-tight text-muted-foreground">{navHelp}</p>
              </AccordionContent>
            </AccordionItem>

            {/* Overlays */}
            <AccordionItem value="overlays">
              <AccordionTrigger className="py-2 px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Overlays
              </AccordionTrigger>
              <AccordionContent className="pt-1 pb-2 px-1 flex flex-col gap-2">
                <label className="flex items-center justify-between gap-2 text-xs font-medium text-muted-foreground">
                  Axes
                  <Switch checked={showAxes} onCheckedChange={setShowAxes} />
                </label>
                <label className="flex items-center justify-between gap-2 text-xs font-medium text-muted-foreground">
                  Camera path
                  <Switch checked={showTrajectory} onCheckedChange={setShowTrajectory} />
                </label>
                <label className="flex items-center justify-between gap-2 text-xs font-medium text-muted-foreground">
                  Keyframe markers
                  <Switch
                    checked={showKeyframeMarkers}
                    onCheckedChange={setShowKeyframeMarkers}
                  />
                </label>

                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">Sphere size</span>
                    <span className="text-xs tabular-nums text-muted-foreground">
                      {(sphereSize * 10).toFixed(2)}
                    </span>
                  </div>
                  <Slider
                    value={[sphereSize * 0.1]}
                    min={MIN_SPHERE_SIZE}
                    max={MAX_SPHERE_SIZE}
                    step={0.0001}
                    onValueChange={(v) => setSphereSize(v[0] * 10)}
                  />
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </Card>
      )}
    </div>
  );
}
