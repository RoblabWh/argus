import type { MappingData } from "@/types/mappingData";
import type { ThermalData } from "@/types/thermalData";
import type { Detection } from "@/types/detection";

export interface Image {
  id: number;
  mapping_report_id: number;
  filename: string;
  url: string;
  thumbnail_url: string;
  created_at?: string;
  uploaded_at?: string;
  width: number;
  height: number;
  coord?: Record<string, unknown>;
  camera_model?: string;
  mappable?: boolean;
  panoramic?: boolean;
  thermal?: boolean;
  mapping_data?: MappingData;
  thermal_data?: ThermalData;
  detections: Detection[];
};

export interface ImageBasic {
  id: number;
  mapping_report_id: number;
  filename: string;
  url: string;
  thumbnail_url: string;
  created_at: string;
  uploaded_at?: string;
  width: number;
  height: number;
  coord?: Record<string, unknown>;
  camera_model?: string;
  mappable?: boolean;
  panoramic?: boolean;
  thermal?: boolean;
  mapping_data?: MappingData;
  thermal_data?: ThermalData;
};


export interface UploadFile {
  file?: File;
  preview?: string;
  progress?: number;
  isExisting?: boolean;
  imageObject?: Partial<Image>; // Assuming Image type has id, filename, thumbnail_url
};
