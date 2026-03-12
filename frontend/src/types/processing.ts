export interface ProcessingSettings {
  keep_weather: boolean;
  fast_mapping: boolean;
  target_map_resolution: number;
  accepted_gimbal_tilt_deviation: number;
  default_flight_height: number | null;
  default_fov: number | null;
  default_cam_pitch: number | null;
  cam_orientation_source: "uav" | "manual";
  default_cam_yaw: number | null;
  default_cam_roll: number | null;
  odm_processing: boolean;
  odm_full: boolean;
  reread_metadata: boolean;
  apply_manual_defaults: boolean;
}
