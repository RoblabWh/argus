export type Weather = {
  id: number;
  mapping_report_id: number;
  open_weather_id: string;
  description?: string;
  temperature?: number;
  humidity?: number;
  pressure?: number;
  wind_speed?: number;
  wind_dir_deg?: number;
  visibility?: number;
  timestamp?: string;
};
