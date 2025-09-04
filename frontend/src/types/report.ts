// src/types/report.ts
import type { Image } from "@/types/image";
import type { Map } from "@/types/map";
import type { Weather } from "@/types/weather";

export interface MappingReport {
  id: number;
  report_id: number;
  flight_timestamp?: string;
  coord?: Record<string, unknown>;
  address?: string;
  flight_duration?: number;
  flight_height?: number;
  covered_area?: number;
  uav?: string;
  image_count?: number;
  images: Image[];
  maps: Map[];
  weather: Weather[];
  webodm_project_id?: string | null;
}

export interface MappingReportSmall {
  id: number;
  report_id: number;
  flight_timestamp?: string;
  coord?: Record<string, unknown>;
  address?: string;
  flight_duration?: number;
  flight_height?: number;
  covered_area?: number;
  uav?: string;
  image_count?: number;
  weather: Weather[];
  webodm_project_id?: string | null;
}

export interface PanoReport {
  id: number;
  report_id: number;
  video_duration?: number;
}

export interface Report {
  report_id: number;
  group_id?: number;
  type: string;
  title: string;
  description: string;
  status: string;
  processing_duration?: number;
  requires_reprocessing?: boolean;
  auto_description?: string;
  created_at: string;
  updated_at: string;
  progress?: number;

  // Optional detail sub-objects
  mapping_report?: MappingReportSmall;
  pano_report?: PanoReport;
}


export interface ReportSummary {
  report_id: number;
  title: string;
  description: string;
  type: string;
  status: string;
  created_at: string;
  flight_timestamp?: string;
  coord?: Record<string, unknown>;
  image_count: number;
  thermal_count: number;
  pano_count: number;
  maps: Map[];
}