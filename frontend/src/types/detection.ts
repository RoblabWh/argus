import type { Coord, GPSCoord, Image } from "@/types/image";

export type Detection = {
  id: number;
  image_id: number;
  class_name: string;
  score: number;
  bbox: Record<string, unknown>;
  image?: Image;
  coord?: Coord;
};


export const DETECTION_COLORS: Record<string, string> = {
  fire: "orange",
  human: "lime",
  vehicle: "cyan",
};
