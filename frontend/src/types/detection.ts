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
