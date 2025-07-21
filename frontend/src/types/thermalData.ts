import type { Image } from "@/types/image";

export type ThermalData = {
  id: number;
  image_id: number;
  counterpart_id: number;
  counterpart_scale: number;
  min_temp: number;
  max_temp: number;
  temp_matrix: number[][] | null; // Stored as JSONB in the database
  temp_embedded?: boolean;
  temp_unit?: string;
  lut_name?: string;
};
