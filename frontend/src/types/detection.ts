import type { Coord, GPSCoord, Image } from "@/types/image";
import { hex } from "motion/react";

export interface Detection {
  id: number;
  image_id: number;
  class_name: string;
  score: number;
  bbox: Record<string, unknown>;
  manually_verified?: boolean;
  image?: Image;
  coord?: Coord;
};


export const DETECTION_COLORS: Record<string, string> = {
  fire: "#FFA500",
  human: "#00FF00",
  vehicle: "#00FFFF",
};

export function getDetectionColor(className: string): string {
  if (className in DETECTION_COLORS) {
    return DETECTION_COLORS[className];
  }
  //calculate a color based on the hash of the class name
  let hash = 0;
  for (let i = 0; i < className.length; i++) {
    hash = className.charCodeAt(i) + ((hash << 5) - hash);
  }
  console.log("Hash for", className, "is", hash, hash % 360);
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
