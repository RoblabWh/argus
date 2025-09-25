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
