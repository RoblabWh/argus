export interface CameraConfigSummary {
  model_name: string;
  auto_discovered: boolean;
  filename: string;
}

export interface GpsConfig {
  lat: string | null;
  lon: string | null;
  rel_alt: string | null;
  alt: string | null;
}

export interface IrConfig {
  ir: string | null;
  ir_value: string | null;
  ir_image_width: string | null;
  ir_image_height: string | null;
  ir_filename_pattern: string | null;
  ir_scale: number | null;
}

export interface CameraPropertiesConfig {
  focal_length: string | null;
  fov: string | null;
}

export interface OrientationConfig {
  cam_roll: string | null;
  cam_yaw: string | null;
  cam_pitch: string | null;
  uav_roll: string | null;
  uav_yaw: string | null;
  uav_pitch: string | null;
}

export interface CameraConfig {
  _model: string;
  _auto_discovered: boolean;
  created_at: string | null;
  width: string | null;
  height: string | null;
  projection_type: string | null;
  gps: GpsConfig;
  ir: IrConfig;
  camera_properties: CameraPropertiesConfig;
  orientation: OrientationConfig;
  fov_correction: number | null;
  adjust_data: boolean;
  rgb_orientation_offset: unknown | null;
  fallbacks: Record<string, unknown>;
}
