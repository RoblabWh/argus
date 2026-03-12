import type { Image } from "@/types/image";

export type MappingData = {
  id: number;
  image_id: number;
  fov: number;
  fov_method?: "exif" | "fallback" | "manual";
  rel_altitude?: number;
  rel_altitude_method: "manual" | "googleelevationapi" | "exif";
  cam_pitch: number;
  cam_pitch_method?: "exif" | "manual";
  cam_roll: number;
  cam_roll_method?: "exif" | "uav";
  cam_yaw: number;
  cam_yaw_method?: "exif" | "uav";
  uav_pitch?: number;
  uav_roll?: number;
  uav_yaw?: number;
  image?: Image;
};
