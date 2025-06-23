import type { Image } from "@/types/image";

export type ThermalData = {
  id: number;
  image_id: number;
  min_temp: number;
  max_temp: number;
  temp_matrix: number[][];
  temp_embedded?: boolean;
  temp_unit?: string;
  lut_name?: string;
  image?: Image;
};
