import { Component, Suspense, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Canvas, useLoader } from "@react-three/fiber";
import { OrbitControls, Bounds, Html, Line } from "@react-three/drei";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";
import type { BufferGeometry } from "three";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import type { Keyframe } from "@/types/reconstruction";

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

const KEYFRAME_SPHERE_RADIUS = 0.05;
const HIGHLIGHT_SCALE = 1.5;
const DEFAULT_POINT_SIZE = 2;
const MIN_POINT_SIZE = 1;
const MAX_POINT_SIZE = 6;

type CloudKind = "sparse" | "dense";

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toFixed(2).padStart(5, "0")}`;
}

interface PointCloudProps {
  url: string;
  pointSize: number;
}

function PointCloud({ url, pointSize }: PointCloudProps) {
  const geometry = useLoader(PLYLoader, url) as BufferGeometry;
  const hasColor = !!geometry.attributes.color;

  return (
    <points geometry={geometry}>
      <pointsMaterial
        size={pointSize}
        sizeAttenuation={false}
        vertexColors={hasColor}
        color={hasColor ? "#ffffff" : "#8ab4f8"}
      />
    </points>
  );
}

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

interface KeyframeMarkersProps {
  keyframes: Keyframe[];
  highlightedIndex: number | null;
  onSelect: (idx: number) => void;
}

function KeyframeMarkers({ keyframes, highlightedIndex, onSelect }: KeyframeMarkersProps) {
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
            <sphereGeometry args={[KEYFRAME_SPHERE_RADIUS, 12, 12]} />
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
      // distanceFactor={2}
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

interface Props {
  results: {
    sparse_pointcloud_url: string | null;
    dense_pointcloud_url: string | null;
    has_dense_pointcloud: boolean;
  };
  keyframes: Keyframe[];
  selectedIndex: number;
  apiUrl: string;
  onOpenViewer: (idx: number) => void;
}

export function ReconstructionPointcloudTab({
  results,
  keyframes,
  selectedIndex,
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
  const [highlightedIndex, setHighlightedIndex] = useState<number | null>(selectedIndex);
  const [retryCounter, setRetryCounter] = useState(0);

  // If sparse url disappears (shouldn't happen) fall back to dense
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

  return (
    <div className="relative w-full h-full">
      <CanvasErrorBoundary
        resetKey={cloudKey}
        onRetry={() => setRetryCounter((c) => c + 1)}
      >
        <Canvas
          frameloop="demand"
          camera={{ fov: 60, near: 0.01, far: 1000, position: [0, 0, 5] }}
          gl={{ antialias: true }}
          onPointerMissed={() => setHighlightedIndex(null)}
        >
          <ambientLight intensity={0.8} />
          <directionalLight position={[5, 10, 5]} intensity={0.6} />
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
            <Bounds fit clip  margin={1.2}>
              {/* key forces remount when switching sparse/dense (or on retry) so useLoader refetches --- REMOVED observe (changed scale on every popup was annoying) */}
              <PointCloud key={cloudKey} url={activeUrl} pointSize={pointSize} />
            </Bounds>
            <Trajectory keyframes={keyframes} />
            <KeyframeMarkers
              keyframes={keyframes}
              highlightedIndex={highlightedIndex}
              onSelect={setHighlightedIndex}
            />
            {highlightedKeyframe && highlightedIndex != null && (
              <KeyframePopup
                keyframe={highlightedKeyframe}
                index={highlightedIndex}
                total={keyframes.length}
                onOpenViewer={onOpenViewer}
                onClose={() => setHighlightedIndex(null)}
              />
            )}
          </Suspense>
          <OrbitControls makeDefault />
        </Canvas>
      </CanvasErrorBoundary>

      {/* Toolbar overlay */}
      <Card className="absolute top-2 left-2 p-3 flex flex-col gap-3 bg-background/85 backdrop-blur-sm shadow-lg z-10 min-w-[200px]">
        {results.has_dense_pointcloud && denseUrl && sparseUrl && (
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
        )}
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
      </Card>
    </div>
  );
}
