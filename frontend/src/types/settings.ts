export interface SettingsData {
  OPEN_WEATHER_API_KEY: string;
  HF_TOKEN: string;
  ENABLE_WEBODM: boolean;
  WEBODM_URL: string;
  WEBODM_USERNAME: string;
  WEBODM_PASSWORD: string;
  DRZ_BACKEND_URL: string;
  DRZ_AUTHOR_NAME: string;
  DRZ_BACKEND_USERNAME: string;
  DRZ_BACKEND_PASSWORD: string;
  /** class_name → #rrggbb. Free-form: the user adds/removes classes in the
   * settings page, and any class absent here gets an automatic color. */
  DETECTION_COLORS: Record<string, string>;
};

export type WebODMSettings = {
  ENABLE_WEBODM: boolean;
  WEBODM_URL: string;
  WEBODM_USERNAME: string;
  WEBODM_PASSWORD: string;
};

export type OpenWeatherSettings = {
  OPEN_WEATHER_API_KEY: string;
};

export type HuggingFaceSettings = {
  HF_TOKEN: string;
};

export type DRZSettings = {
  BACKEND_URL: string;
  AUTHOR_NAME: string;
  BACKEND_USERNAME: string;
  BACKEND_PASSWORD: string;
};

export type SettingsTestResult = {
  success: boolean;
  message: string;
  detail: string | null;
  latency_ms: number | null;
};
