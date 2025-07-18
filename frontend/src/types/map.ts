import type { MapElement } from "@/types/mapElement";

export type Map = {
  id: number;
  mapping_report_id: number;
  name: string;
  url: string;
  bounds: {
    gps: {
      latitude_min: number;
      latitude_max: number;
      longitude_min: number;
      longitude_max: number;
    },
    utm?: {
      crs: string;
      zone: number;
      zone_letter: string;
      hemisphere: "N" | "S";
      easting_min: number;
      easting_max: number;
      northing_min: number;
      northing_max: number;
    };
    corners: {
      gps: [number, number][];
      utm?: [number, number][];
    };
  };

  created_at: string;
  map_elements?: MapElement[];
};
