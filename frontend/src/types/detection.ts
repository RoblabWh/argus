import type { Coord, GPSCoord, Image } from "@/types/image";
import { hex } from "motion/react";
export interface Detection {
  id: number;
  image_id: number;
  class_name: string;
  score: number;
  bbox: Record<string, unknown>;
  manually_verified?: boolean;
  /** Re-identification cluster label grouping the same physical object across overlapping
   * images, scoped to one report. null/undefined = not yet assigned. */
  unique_object_id?: number | null;
  image?: Image;
  coord?: Coord;
};

/**
 * How detections are reduced for display on the map and counted in the DetectionCard.
 * - "all": every detection shown individually (no grouping, no clipping)
 * - "reduced": merge by unique_object_id into clusters, Voronoi-clip the ungrouped leftovers
 */
export type DetectionDisplayMode = "all" | "reduced";


function parseHex(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  return [r, g, b];
}

export const DETECTION_COLORS: Record<string, string> = {
  fire: "#FFA500",
  human: "#00FF00",
  vehicle: "#00FFFF",
};

export function getDetectionColor(className: string, muted: boolean | undefined): string {
  if (className in DETECTION_COLORS) {
    if (muted) {
      const rgb = parseHex(DETECTION_COLORS[className]);; // set alpha to 50%
      return `rgba(${rgb[0]*255}, ${rgb[1]*255}, ${rgb[2]*255}, 0.5)`;
    }
    return DETECTION_COLORS[className];
  }
  //calculate a color based on the hash of the class name
  let hash = 0;
  for (let i = 0; i < className.length; i++) {
    hash = className.charCodeAt(i) + ((hash << 5) - hash);
  }
  console.log("Hash for", className, "is", hash, hash % 360);
  if (muted) {
    return `hsl(${(hash / 2) % 360}, 0%, 42%)`;
  }
  const color = `hsl(${(hash / 2) % 360}, 90%, 60%)`;
  return color;
}

/** Classes produced by the dedicated fire detection pipeline (mirrors the
 * backend's FIRE_CLASSES). On the map they render as the fire overlay, not
 * as individual markers; the slideshow still draws their bboxes. */
export const FIRE_CLASSES = new Set(["fire"]);

/** Plasma sequential ramp for the fire overlay: perceptually uniform and
 * monotonic in lightness — purple = low confidence, bright yellow = high. */
const CONFIDENCE_RAMP: [number, [number, number, number]][] = [
  [0.0, [13, 8, 135]],    // #0d0887
  [0.25, [126, 3, 168]],  // #7e03a8
  [0.5, [204, 71, 120]],  // #cc4778
  [0.75, [248, 149, 64]], // #f89540
  [1.0, [240, 249, 33]],  // #f0f921
];

export function confidenceToColor(score: number): string {
  const t = Math.min(Math.max(score, 0), 1);
  for (let i = 1; i < CONFIDENCE_RAMP.length; i++) {
    const [t1, c1] = CONFIDENCE_RAMP[i];
    if (t > t1) continue;
    const [t0, c0] = CONFIDENCE_RAMP[i - 1];
    const f = (t - t0) / (t1 - t0);
    const rgb = c0.map((v, ch) => Math.round(v + f * (c1[ch] - v)));
    return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
  }
  return "rgb(240, 249, 33)";
}

/** CSS gradient of the confidence ramp, for the fire overlay legend. */
export const CONFIDENCE_RAMP_GRADIENT = `linear-gradient(to right, ${CONFIDENCE_RAMP.map(
  ([t, [r, g, b]]) => `rgb(${r}, ${g}, ${b}) ${t * 100}%`,
).join(", ")})`;

export interface FireMapRegionImage {
  image_id: number;
  filename?: string | null;
  thumbnail_url?: string | null;
}

export interface FireMapRegion {
  max_score: number;
  detection_count: number;
  images: FireMapRegionImage[];
}

/** Response of GET /detections/r/{id}/fire_map — see api/app/services/fire_map.py. */
export interface FireMap {
  geojson: import("geojson").FeatureCollection | null;
  regions: Record<string, FireMapRegion>;
}

export interface Geometry {
    type: "Point"
    coordinates: [number, number] // [longitude, latitude]
}

export interface Properties {
    type: string
    subtype: string
    detection: number
    name: string
    description: string
    datetime: string
}
