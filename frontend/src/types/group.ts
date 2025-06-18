import type { Report } from "@/types/report";

export interface Group {
  id: number;
  name: string;
  description?: string;
  created_at: string;
  reports: Report[];
}
