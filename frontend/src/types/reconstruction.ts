export interface ReconstructionSettings {
  preset: "sparse" | "dense_fast" | "dense_detail";
  frame_step: number;
  config_overrides: Record<string, unknown>;
  flip_video: boolean;
}

export interface Keyframe {
  filename: string;
  url: string;
  timestamp: number;
  tx?: number;
  ty?: number;
  tz?: number;
  qx?: number;
  qy?: number;
  qz?: number;
  qw?: number;
}

export interface ReconstructionResults {
  report_id: number;
  keyframe_count: number;
  keyframes: Keyframe[];
  has_dense_pointcloud: boolean;
  sparse_pointcloud_url: string | null;
  dense_pointcloud_url: string | null;
}

export interface VideoUploadResult {
  status: "uploaded" | "skipped" | "error";
  filename: string;
  message: string | null;
}

export interface ImageUploadResult {
  status: "success" | "error" | "duplicate";
  filename: string;
  error: string | null;
  image_object?: {
    id: number;
    filename: string;
    thumbnail_url: string;
    mapping_data?: unknown;
    [key: string]: unknown;
  };
}

export interface UploadSummary {
  report_type: "mapping" | "reconstruction_360" | "unchanged";
  images: ImageUploadResult[];
  video: VideoUploadResult | null;
  warnings: string[];
}
