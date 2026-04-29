import { useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Play } from "lucide-react";
import type { Keyframe } from "@/types/reconstruction";

function toThumbnailUrl(url: string): string {
  const lastSlash = url.lastIndexOf("/");
  return url.slice(0, lastSlash + 1) + "thumbnails/" + url.slice(lastSlash + 1);
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

interface Props {
  keyframes: Keyframe[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  onPlayFromHere?: (index: number) => void;
  apiUrl: string;
}

export function KeyframeListCard({ keyframes, selectedIndex, onSelect, onPlayFromHere, apiUrl }: Props) {
  const selectedRef = useRef<HTMLButtonElement | null>(null);

  // Scroll selected thumbnail into view when index changes programmatically
  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedIndex]);

  return (
    <Card className="flex-1 min-h-0 flex flex-col px-4 py-3 m-0">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2 shrink-0">
        Keyframes ({keyframes.length})
      </p>

      {keyframes.length === 0 ? (
        <CardContent className="px-0 py-4 text-sm text-muted-foreground">
          No keyframes available.
        </CardContent>
      ) : (
        <div className="overflow-y-auto flex-1 -mx-1">
          <div className="grid grid-cols-[repeat(auto-fill,minmax(90px,1fr))] gap-1.5 px-1 pb-2">
            {keyframes.map((kf, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div key={kf.filename} className="relative group">
                  <button
                    ref={isSelected ? selectedRef : null}
                    onClick={() => onSelect(idx)}
                    className={`relative w-full rounded-md overflow-hidden aspect-video focus:outline-none transition-all ${
                      isSelected
                        ? "ring-2 ring-primary ring-offset-1"
                        : "ring-1 ring-border hover:ring-primary/50"
                    }`}
                    title={`Keyframe ${idx + 1} — ${formatTimestamp(kf.timestamp)}`}
                  >
                    <img
                      src={`${apiUrl}${toThumbnailUrl(kf.url)}`}
                      onError={(e) => {
                        const img = e.currentTarget;
                        img.onerror = null;
                        img.src = `${apiUrl}${kf.url}`;
                      }}
                      alt={`Keyframe ${idx + 1}`}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                    {/* Timestamp badge */}
                    <span className="absolute bottom-0.5 right-0.5 bg-black/60 text-white text-[9px] leading-none px-1 py-0.5 rounded">
                      {formatTimestamp(kf.timestamp)}
                    </span>
                    {/* Index badge on selected */}
                    {isSelected && (
                      <span className="absolute top-0.5 left-0.5 bg-primary text-primary-foreground text-[9px] leading-none px-1 py-0.5 rounded">
                        {idx + 1}
                      </span>
                    )}
                  </button>

                  {/* Play-from-here button — shown on hover when callback is provided */}
                  {onPlayFromHere && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onPlayFromHere(idx);
                      }}
                      title={`Watch video from ${formatTimestamp(kf.timestamp)}`}
                      className="absolute top-0.5 right-0.5 opacity-0 group-hover:opacity-100 transition-opacity bg-black/70 hover:bg-black/90 text-white rounded p-0.5"
                    >
                      <Play className="w-2.5 h-2.5 fill-current" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}
