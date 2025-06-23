import type { Image } from "@/types/image";

export type Detection = {
  id: number;
  image_id: number;
  class_name: string;
  score: number;
  bbox: Record<string, unknown>;
  image?: Image;
};
