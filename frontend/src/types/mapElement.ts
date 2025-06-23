import type { Map } from "@/types/map";
// import type { ImageOut } from "@/types/image"; // Uncomment if needed

export type MapElement = {
  id: number;
  map_id: number;
  image_id: number;
  index: number;
  coord: Record<string, unknown>;
  corners: Record<string, unknown>;
  px_coord: Record<string, unknown>;
  px_corners: Record<string, unknown>;
  map?: Map;
  // image?: ImageOut;
};
