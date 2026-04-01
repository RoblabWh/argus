import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Film, Layers, Gauge, Timer, LayoutGrid, Clock, Globe, ImageIcon, Camera} from "lucide-react";
import { CirclePile } from 'lucide-react';
import type { ReconstructionReport } from "@/types/report";

const PRESET_LABELS: Record<string, string> = {
  sparse: "Sparse (fast)",
  dense_fast: "Dense — Fast (640×320)",
  dense_detail: "Dense — Detail (1440×720)",
};

function formatDuration(seconds: number | undefined): string {
  if (seconds == null) return "N/A";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function extractFilename(path: string): string {
  return path.split("/").pop() ?? path;
}

interface Props {
  reconstructionReport: ReconstructionReport;
}

export function VideoInfoCard({ reconstructionReport }: Props) {
  const {
    video_path,
    video_duration,
    keyframe_count,
    processing_settings,
    has_dense_pointcloud,
    flight_timestamp,
    camera_model,
  } = reconstructionReport;



  return (


    <Card className="min-w-48 max-w-114 flex-1 relative overflow-hidden pb-3">
      {/* Background UAV Icon */}
      <Globe className="absolute right-2 top-1 w-24 h-24 opacity-100 text-muted-foreground dark:text-white z-0 pointer-events-none" />

      {/* Gradient Overlay */}
      {/* <div className="absolute inset-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/60 to-white/0 dark:from-gray-900/100 dark:via-gray-900/70 dark:to-gray-900/0" /> */}
      <div className="absolute w-40 h-30 right-0 top-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/75 to-white/55 dark:from-gray-900/100 dark:via-gray-900/85 dark:to-gray-900/60" />

      <CardContent className="px-4 pt-1 flex flex-col items-start space-y-1 relative z-10">
        {/* Header */}
        <div className="flex justify-between items-start w-full">
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="text-xl font-bold leading-none whitespace-nowrap truncate">360 Video</div>
            </TooltipTrigger>
            <TooltipContent>
              <p>{camera_model ?? "Unknown camera"}</p>
            </TooltipContent>
          </Tooltip>
        </div>


        {/* Flight Stats */}
        <div className="flex flex-col mt-2 gap-[0.2rem] text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Clock className="w-3 h-3" />
            Duration: {formatDuration(video_duration)}
          </div>
          <div className="flex items-center gap-2">
            <ImageIcon className="w-3 h-3" />
            Keyframes: {keyframe_count}
          </div>
          <div className="flex items-center gap-2">
            <CirclePile className="w-3 h-3" />
            Point Cloud: {has_dense_pointcloud ? "Dense" : "Sparse"}
          </div>
          
          <div className="flex items-center gap-2">
            <Camera className="w-3 h-3" />
            Camera: {camera_model ?? "Unknown camera"}
          </div>
        </div>


        {/* Footer */}
        <div className="w-full text-right mt-0 flex justify-end text-[10px] text-muted-foreground">
          <span>{flight_timestamp ? `Flown at ${new Date(flight_timestamp).toLocaleString()}` : "Flight date unknown"}</span>
        </div>
      </CardContent>
    </Card>
  );
}

// const Panorama360Icon = ({
//   size = 24,
//   color = "currentColor",
//   strokeWidth = 2,
//   className,
//   style,
//   ...rest
// }) => {

//   return (
//     <svg
//       xmlns="http://www.w3.org/2000/svg"
//       width={size}
//       height={size}
//       viewBox="0 0 24 24"
//       fill="none"
//       stroke={color}
//       strokeWidth={strokeWidth}
//       strokeLinecap="round"
//       strokeLinejoin="round"
//       className={className}
//       style={style}
//       {...rest}
//     >
//       <defs>
//         {/* Clip photo content tightly inside the sphere */}
//         <clipPath id="clipId">
//           <circle cx="12" cy="12" r="9.9" />
//         </clipPath>
//       </defs>

//       {/* ── Globe ring ───────────────────────────────────────────── */}
//       <circle cx="12" cy="12" r="10" />

//       {/*
//         ── Brow arc — top cap of the globe ──────────────────────────
//         Endpoints (4,6) and (20,6) lie exactly on the globe circle.
//         CCW sweep (0,0) curves UP through (12,4) → concave-down ∩ dome.
//       */}
//       <path d="M 4,6 A 8,2 0 0,0 20,6" />

//       {/*
//         ── Chin arc — bottom cap ────────────────────────────────────
//         Endpoints (4,18) and (20,18) also on the globe circle.
//         CW sweep (0,1) curves DOWN through (12,20) → concave-up ∪ bowl.
//       */}
//       <path d="M 4,18 A 8,2 0 0,1 20,18" />

//       {/* ── Photo content — clipped to sphere ──────────────────── */}
//       <g clipPath="url(#clipId)" stroke="none">
//         {/*
//           Mountain silhouette: a single connected ridge with two peaks.
//           Left peak higher (9,10.5), right peak lower (15.5,13).
//           Valley at (13,17) keeps the saddle visible.
//           Base runs along y=18 (the chin arc endpoints).
//         */}
//         <path
//           d="M 4,18 L 9,10.5 L 13,17 L9,16 Z"
//           fill={color}
//         />
//         <path
//           d="M 9,17 L 13.5,13 L 16,16 Z"
//           fill={color}
//         />

//         {/* Sun — filled dot in upper-right of the photo area */}
//         <circle cx="16.5" cy="9" r="1.4" fill={color} />
//       </g>
//     </svg>
//   );
// };