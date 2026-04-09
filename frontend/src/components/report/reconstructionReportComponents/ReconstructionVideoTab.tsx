import { useEffect, useRef, useState } from "react";
import { Viewer } from "@photo-sphere-viewer/core";
import "@photo-sphere-viewer/core/index.css";
import { EquirectangularVideoAdapter } from "@photo-sphere-viewer/equirectangular-video-adapter";
import { VideoPlugin, events as VideoEvents } from "@photo-sphere-viewer/video-plugin";
import "@photo-sphere-viewer/video-plugin/index.css";
import { Video, VideoOff } from "lucide-react";

interface Orientation {
  yaw: number;
  pitch: number;
}

interface Props {
  videoUrl: string;
  seekTime: number | null;
  /** Rotate to this orientation on seek — only set when triggered from the Viewer "Watch Video" button. */
  orientation: Orientation | null;
  /** When false, auto-pause the video (e.g. user switched to another tab). */
  isActive: boolean;
}

export function ReconstructionVideoTab({ videoUrl, seekTime, orientation, isActive }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const videoPluginRef = useRef<VideoPlugin | null>(null);
  const viewerReadyRef = useRef(false);
  // Tracks whether we already froze near the end; reset when user seeks back.
  const endedRef = useRef(false);
  const [codecError, setCodecError] = useState(false);

  // Keep latest values accessible in the ready callback without re-running init
  const seekTimeRef = useRef<number | null>(null);
  seekTimeRef.current = seekTime;
  const orientationRef = useRef<Orientation | null>(null);
  orientationRef.current = orientation;

  // Initialise PSV with EquirectangularVideoAdapter + VideoPlugin once on mount
  useEffect(() => {
    if (!videoUrl) return;

    let viewer: Viewer | null = null;
    setCodecError(false);
    endedRef.current = false;

    const timeout = setTimeout(() => {
      if (!containerRef.current || viewerRef.current) return;

      viewer = new Viewer({
        container: containerRef.current,
        adapter: EquirectangularVideoAdapter,
        panorama: { source: videoUrl },
        navbar: true,
        plugins: [
          [VideoPlugin, { progressbar: true, bigbutton: true }],
        ],
      });

      viewerRef.current = viewer;
      videoPluginRef.current = viewer.getPlugin(VideoPlugin);

      viewer.addEventListener("ready", () => {
        viewerReadyRef.current = true;

        const plugin = videoPluginRef.current;
        if (!plugin) return;

        // Start muted (drone video is usually just wind/motor noise)
        plugin.setMute(true);

        // Belt-and-suspenders: try to override the adapter's hardcoded loop=true via private prop.
        // If this succeeds, the ProgressEvent handler below becomes a no-op safety net.
        const videoEl = (plugin as unknown as { video?: HTMLVideoElement }).video;
        if (videoEl) {
          videoEl.loop = false;
          videoEl.addEventListener("error", () => {
            console.error("[PSV Video] Native video error:", videoEl.error);
            setCodecError(true);
          });
        }

        // Reliable loop-prevention via public ProgressEvent API:
        // equirectangular-video-adapter hardcodes loop=true on the <video> element,
        // so we catch near-end progress and force-pause + seek to last frame.
        plugin.addEventListener(VideoEvents.ProgressEvent.type, (e) => {
          const nearEnd = e.duration > 0 && e.time >= e.duration - 0.15;
          if (nearEnd && !endedRef.current) {
            endedRef.current = true;
            plugin.pause();
            plugin.setTime(e.duration);  // freeze on last frame
          } else if (e.progress < 0.95) {
            endedRef.current = false;    // reset when user seeks back
          }
        });

        // Apply any seek+orientation that was requested before the viewer was ready
        const pendingSeek = seekTimeRef.current;
        if (pendingSeek !== null) {
          plugin.setTime(pendingSeek);
          plugin.play();
          const pendingOrientation = orientationRef.current;
          if (pendingOrientation) viewer?.rotate(pendingOrientation);
        }
      }, { once: true });

      viewer.addEventListener("error", (e) => {
        console.error("[PSV Video] Viewer error:", e);
        setCodecError(true);
      });
    }, 0);

    return () => {
      clearTimeout(timeout);
      const toDestroy = viewer;
      viewerRef.current = null;
      videoPluginRef.current = null;
      viewerReadyRef.current = false;
      endedRef.current = false;
      try { toDestroy?.destroy(); } catch { /* ignore PSV cleanup errors during navigation */ }
    };
  }, [videoUrl]);

  // Seek + rotate when seekTime changes (explicit "Play from here" actions only)
  useEffect(() => {
    if (seekTime === null) return;
    const plugin = videoPluginRef.current;
    const viewer = viewerRef.current;
    if (!plugin || !viewer || !viewerReadyRef.current) return;

    endedRef.current = false;  // allow playing to end again after a manual seek
    plugin.setTime(seekTime);
    plugin.play();
    if (orientationRef.current) viewer.rotate(orientationRef.current);
  }, [seekTime]);

  // Auto-pause when the user switches away from the Video tab
  useEffect(() => {
    if (!isActive && videoPluginRef.current?.isPlaying()) {
      videoPluginRef.current.pause();
    }
  }, [isActive]);

  if (!videoUrl) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
        <Video className="w-12 h-12" />
        <p className="text-sm">No video available for this report.</p>
      </div>
    );
  }

  if (codecError) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
        <VideoOff className="w-12 h-12" />
        <p className="text-sm font-medium">Video cannot be played in this browser.</p>
        <p className="text-xs max-w-xs text-center">
          The video may use the HEVC/H.265 codec which is not supported by all browsers.
          Re-processing the video will convert it to H.264.
        </p>
      </div>
    );
  }

  return <div ref={containerRef} className="w-full h-full" />;
}
