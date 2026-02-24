import type { Map } from "@/types/map";
// import type { ImageOut } from "@/types/image"; // Uncomment if needed

export type MapElement = {
  id: number;
  map_id: number;
  image_id: number;
  index: number;
  coord: Record<string, unknown>;
  corners: {
    gps: [number, number][];
    utm?: [number, number][];
  };
  px_coord: Record<string, unknown>;
  px_corners: Record<string, unknown>;
  voronoi_gps?: [number, number][];
  map?: Map;
  // image?: ImageOut;
};
