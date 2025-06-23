import type { MapElement } from "@/types/mapElement";

export type Map = {
  id: number;
  report_id: number;
  name: string;
  url: string;
  status?: string;
  created_at: string;
  map_elements: MapElement[];
};
