export type Weather = {
  id: number;
  report_id: number;
  coord?: Record<string, unknown>;
  temperature?: number;
  humidity?: number;
  air_pressure?: number;
  wind_speed?: number;
  wind_dir_deg?: number;
  visibility?: number;
  cloud_cover?: number;
  weather_condition?: string;
  timestamp?: string; // ISO string from backend
};
