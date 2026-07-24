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
  temp_unit?: "C" | "F";
  lut_name?: string;
};

export interface ThermalMapRegionImage {
  image_id: number;
  filename?: string | null;
  thumbnail_url?: string | null;
}

export interface ThermalMapRegion {
  max_temp: number;
  images: ThermalMapRegionImage[];
}

/** Response of GET /reports/{id}/thermal_map — see api/app/services/thermal_map.py. */
export interface ThermalMap {
  geojson: import("geojson").FeatureCollection | null;
  regions: Record<string, ThermalMapRegion>;
  /** Unclipped temperature range of the report's thermal data (filter hint). */
  range: { min: number; max: number } | null;
}
