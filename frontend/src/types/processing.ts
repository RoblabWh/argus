export interface ProcessingSettings {
  keep_weather: boolean;
  fast_mapping: boolean;
  target_map_resolution: number;
  accepted_gimbal_tilt_deviation: number;
  default_flight_height: number;
  odm_processing: boolean;
  odm_full: boolean;
  reread_metadata: boolean;
}