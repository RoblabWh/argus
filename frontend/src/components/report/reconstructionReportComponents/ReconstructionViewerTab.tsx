import { useEffect, useRef, useCallback } from "react";
import { Viewer } from "@photo-sphere-viewer/core";
import "@photo-sphere-viewer/core/index.css";
import { MarkersPlugin } from "@photo-sphere-viewer/markers-plugin";
import "@photo-sphere-viewer/markers-plugin/index.css";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Clapperboard } from "lucide-react";
import type { Keyframe } from "@/types/reconstruction";

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toFixed(2).padStart(5, "0")}`;
}

/**
 * Rotates world-space vector (vx,vy,vz) into camera space using TUM-format
 * quaternion (qx,qy,qz,qw) representing the world-to-camera rotation.
 * Uses the quaternion sandwich product: v' = q v q*
 */
function quatRotate(
  qx: number, qy: number, qz: number, qw: number,
  vx: number, vy: number, vz: number
): { x: number; y: number; z: number } {
  // t = 2 * cross(q_vec, v)
  const tx = 2 * (qy * vz - qz * vy);
  const ty = 2 * (qz * vx - qx * vz);
  const tz = 2 * (qx * vy - qy * vx);
  // result = v + qw*t + cross(q_vec, t)
  return {
    x: vx + qw * tx + (qy * tz - qz * ty),
    y: vy + qw * ty + (qz * tx - qx * tz),
    z: vz + qw * tz + (qx * ty - qy * tx),
  };
}

/**
 * Computes PSV yaw/pitch (radians) pointing from the current keyframe toward
 * a target keyframe, using TUM/OpenCV camera convention (+Z forward, +Y down).
 * Returns null if either pose is incomplete or cameras are coincident.
 */
function computeMarkerAngles(
  current: Keyframe,
  target: Keyframe
): { yaw: number; pitch: number; distance: number } | null {
  if (
    current.tx == null || current.ty == null || current.tz == null ||
    current.qx == null || current.qy == null || current.qz == null || current.qw == null ||
    target.tx == null  || target.ty == null  || target.tz == null
  ) return null;

  const dx = target.tx - current.tx;
  const dy = target.ty - current.ty;
  const dz = target.tz - current.tz;
  const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
  if (dist < 1e-6) return null;

  const cam = quatRotate(
    // 0,0,0,1.0,
   current.qx, current.qy, current.qz, current.qw,
    dx / dist, dy / dist, dz / dist
  );

  return {
    yaw:   Math.atan2(cam.x, cam.z),
    // Negate Y: OpenCV Y is down, PSV pitch > 0 is up
    pitch: -Math.atan2(cam.y, Math.sqrt(cam.x * cam.x + cam.z * cam.z)),
    distance: dist,
  };
}

/**
 * Maps a normalized value [0..1] to an HSL color string.
 * 0 → blue (hue 240°), 1 → red (hue 0°).
 */
function normalizedToHsl(t: number): string {
  const hue = Math.round((1 - t) * 240);
  return `hsl(${hue}, 100%, 55%)`;
}

function scale(d: number, min: number = 8, max: number = 20, maxDistance: number = 5): number {
  const t = Math.max(0, 1 - d / maxDistance);
  return min + (max - min) * t * t;
}

function colorBetween(startHue: number, endHue: number, factor: number): string {
  const hue = startHue + (endHue - startHue) * factor;
  return `hsl(${hue * 360}, 100%, 55%)`;
}

function computeMarkersForIndex(keyframes: Keyframe[], selectedIndex: number) {
  const currentKf = keyframes[selectedIndex];
  const timestamps = keyframes.map((kf) => kf.timestamp);
  const minTs = Math.min(...timestamps);
  const maxTs = Math.max(...timestamps);
  const tsRange = maxTs - minTs || 1;

  return keyframes.flatMap((targetKf, targetIdx) => {
    if (targetIdx === selectedIndex) return [];
    if (targetKf.tx == null) return [];

    const angles = computeMarkerAngles(currentKf, targetKf);
    if (!angles) return [];
    const size = scale(angles.distance, 8, 55, 2);
    const color = colorBetween(0.5, 0.8, (targetKf.timestamp - minTs) / tsRange);

    return [{
      id: `kf-${targetIdx}`,
      position: { yaw: angles.yaw, pitch: angles.pitch },
      html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};opacity:0.4;border:1.5px solid rgba(255,255,255,0.8);box-shadow:0 0 4px rgba(0,0,0,0.5);cursor:pointer;"></div>`,
      size: { width: size, height: size },
      scale: [0.5, 4],
      // anchor: "center center",
      tooltip: {
        content: `Frame ${targetIdx + 1} — ${formatTimestamp(targetKf.timestamp)}`,
        position: "top center",
      },
      data: { targetIndex: targetIdx },
    }];
  });
}

interface Props {
  keyframes: Keyframe[];
  selectedIndex: number;
  onNavigate: (index: number) => void;
  apiUrl: string;
}

export function ReconstructionViewerTab({ keyframes, selectedIndex, onNavigate, apiUrl }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const currentIndexRef = useRef<number>(-1);
  // Always reflects the latest selectedIndex without triggering init effect
  const selectedIndexRef = useRef<number>(selectedIndex);
  selectedIndexRef.current = selectedIndex;
  // Stable callback ref — prevents stale closure in the select-marker listener
  const onNavigateRef = useRef(onNavigate);
  onNavigateRef.current = onNavigate;
  // True once PSV has fired its 'ready' event — guards setMarkers from running during initial panorama load
  const viewerReadyRef = useRef<boolean>(false);

  const markersPluginRef = useRef<MarkersPlugin | null>(null);

  const currentKeyframe = keyframes[selectedIndex];
  const total = keyframes.length;

  const goTo = useCallback(
    (idx: number) => {
      const clamped = Math.max(0, Math.min(total - 1, idx));
      if (clamped !== selectedIndex) onNavigate(clamped);
    },
    [total, selectedIndex, onNavigate]
  );

  // Initialise PSV viewer once on mount.
  // Wrapped in setTimeout(0) to survive React StrictMode's mount→cleanup→remount cycle:
  // StrictMode cleanup runs clearTimeout() before the timeout fires, preventing double-init.
  // In production (no StrictMode), the timeout fires normally after the first mount.
  useEffect(() => {
    if (total === 0) return;

    let viewer: Viewer | null = null;

    const timeout = setTimeout(() => {
      if (!containerRef.current || viewerRef.current) return;

      const startIdx = selectedIndexRef.current;
      viewerReadyRef.current = false;

      const panoramaUrl = `${apiUrl}${keyframes[startIdx].url}`;
      console.log("[PSV] Initializing viewer at index", startIdx, "| container:", containerRef.current.offsetWidth, "x", containerRef.current.offsetHeight);
      console.log("[PSV] Panorama URL:", panoramaUrl);

      viewer = new Viewer({
        container: containerRef.current,
        panorama: panoramaUrl,
        minFov: 20,
        maxFov: 150,
        navbar: true,
        plugins: [MarkersPlugin],
      });
      viewerRef.current = viewer;
      currentIndexRef.current = startIdx;

      markersPluginRef.current = viewer.getPlugin(MarkersPlugin);

      // Register click listener once; onNavigateRef keeps it from going stale
      markersPluginRef.current.addEventListener("select-marker", ({ marker }) => {
        const idx: number | undefined = marker.data?.targetIndex;
        if (typeof idx === "number") onNavigateRef.current(idx);
      });

      // Set markers only after PSV has finished loading the first panorama.
      // Calling setMarkers during initial load blocks PSV's internal state.
      viewer.addEventListener("ready", () => {
        console.log("[PSV] ready event fired — setting initial markers");
        viewerReadyRef.current = true;
        const plugin = markersPluginRef.current;
        if (plugin) plugin.setMarkers(computeMarkersForIndex(keyframes, selectedIndexRef.current));
      }, { once: true });

      viewer.addEventListener("error", (e) => {
        console.error("[PSV] Viewer error:", e);
      });
    }, 0);

    return () => {
      clearTimeout(timeout);  // cancels deferred init if StrictMode cleanup fires first
      viewer?.destroy();      // destroys viewer if it was already created
      viewerRef.current = null;
      markersPluginRef.current = null;
      currentIndexRef.current = -1;
      viewerReadyRef.current = false;
    };
  }, [keyframes]); // only re-run when keyframes arrive or change

  // Update panorama when selectedIndex changes (no destroy/recreate)
  useEffect(() => {
    if (!viewerRef.current || total === 0) return;
    if (currentIndexRef.current === selectedIndex) return;

    const url = `${apiUrl}${keyframes[selectedIndex].url}`;
    viewerRef.current.setPanorama(url, { showLoader: true });
    currentIndexRef.current = selectedIndex;
  }, [selectedIndex, apiUrl, keyframes, total]);

  // Update markers whenever the current frame changes.
  // Guarded by viewerReadyRef — skips if PSV hasn't fired 'ready' yet.
  // The initial setMarkers call after the first panorama loads is handled by the 'ready' listener above.
  useEffect(() => {
    const plugin = markersPluginRef.current;
    if (!plugin || total === 0 || !viewerReadyRef.current) return;

    console.log("[PSV] setMarkers called for index", selectedIndex, "| markerCount:", keyframes.length - 1);
    plugin.setMarkers(computeMarkersForIndex(keyframes, selectedIndex));
  }, [selectedIndex, keyframes, total]);

  // Keyboard navigation
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      const tag = (document.activeElement as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (e.key === "ArrowLeft") {
        e.preventDefault();
        goTo(selectedIndex - 1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        goTo(selectedIndex + 1);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [goTo, selectedIndex]);

  if (total === 0) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
        <Clapperboard className="w-12 h-12" />
        <p className="text-sm">No keyframes — processing may still be running.</p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full select-none">
      {/* PSV container */}
      <div ref={containerRef} className="w-full h-full" />

      {/* Bottom navigation — Previous | [counter] | Next */}
      <div className="absolute bottom-12 left-1/2 -translate-x-1/2 z-10 flex items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => goTo(selectedIndex - 1)}
          disabled={selectedIndex === 0}
          className="bg-black/50 hover:bg-black/70 text-white border-white/20 backdrop-blur-sm"
        >
          <ChevronLeft className="w-4 h-4 mr-1" />
          Previous
        </Button>

        <div className="bg-black/50 text-white text-xs px-3 py-1.5 rounded-full backdrop-blur-sm flex items-center gap-2 pointer-events-none">
          <span className="font-medium">{selectedIndex + 1} / {total}</span>
          {currentKeyframe && (
            <>
              <span className="opacity-50">|</span>
              <span>{formatTimestamp(currentKeyframe.timestamp)}</span>
            </>
          )}
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => goTo(selectedIndex + 1)}
          disabled={selectedIndex === total - 1}
          className="bg-black/50 hover:bg-black/70 text-white border-white/20 backdrop-blur-sm"
        >
          Next
          <ChevronRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  );
}
