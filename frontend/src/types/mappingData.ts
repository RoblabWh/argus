import type { Image } from "@/types/image";

export type MappingData = {
  id: number;
  image_id: number;
  fov: number;
  rel_altitude?: number;
  rel_altitude_method: "manual" | "googleelevationapi" | "exif";
  cam_pitch: number;
  cam_roll: number;
  cam_yaw: number;
  uav_pitch?: number;
  uav_roll?: number;
  uav_yaw?: number;
  image?: Image;
};
