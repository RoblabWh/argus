// src/api/groups.ts
import type { Group } from "@/types/group";
import type { Report, ReportSummary } from "@/types/report";
import type { Map } from "@/types/map";
import type { ProcessingSettings } from "@/types/processing";
import type { Image } from "@/types/image";
//
import { data } from "react-router-dom";
import type { Detection } from "./types";

// const API_URL = "http://" + process.env.VITE_API_URL + ":" + process.env.VITE_API_PORT;
// const API_URL = "http://localhost:8000";
const API_URL = import.meta.env.VITE_API_URL ;

async function fetchJson<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${API_URL}${endpoint}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${endpoint}: ${res.status}`);
  }
  return res.json();
}

async function postJson<T>(
  endpoint: string,
  data: unknown,
  method: "POST" | "PUT" | "PATCH" = "POST"
): Promise<T> {
  const res = await fetch(`${API_URL}${endpoint}`, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    throw new Error(`Failed to ${method} ${endpoint}: ${res.status}`);
  }

  return res.json();
}

async function deleteRequest(
  endpoint: string
): Promise<void> {
  const res = await fetch(`${API_URL}${endpoint}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    let msg = `Failed to DELETE ${endpoint}: ${res.status}`;
    try {
      const json = await res.json();
      msg += ` - ${json.detail || JSON.stringify(json)}`;
    } catch {
      // Ignore JSON parse error
    }
    throw new Error(msg);
  }
}

export const getGroups = () => fetchJson<Group[]>("/groups/");
export const getGroup = (id: number) => fetchJson<Group>(`/groups/${id}`);
export const getGroupReports = (id: number) => fetchJson<Report[]>(`/groups/${id}/reports`);
export const createGroup = (data: { name: string; description: string }) => postJson<Group>("/groups/", data);
export const getSummaryReports = (group_id: number) => fetchJson<ReportSummary[]>(`/groups/${group_id}/summary`);
export const deleteGroup = (id: number) => deleteRequest(`/groups/${id}`);
export const editGroup = (data: { id: number; name: string; description: string }) => postJson<Group>(`/groups/${data.id}`, data, "PUT");

export const getReport = (report_id: number) => fetchJson<Report>(`/reports/${report_id}`);
export const createReport = (data: { group_id: number; title: string; description: string }) =>  postJson<Report>(`/reports/`, data);
export const deleteReport = (report_id: number) => deleteRequest(`/reports/${report_id}`);
export const editReport = (data: { id: number; title: string; description: string }) => {return postJson<Report>(`/reports/${data.id}`, data, "PUT");};

export const getMaps = (report_id: number) => fetchJson<Map[]>(`/reports/${report_id}/mapping_report/maps`);
export const getODMProjectID = (report_id: number) => fetchJson<{ webodm_project_id: string }>(`/reports/${report_id}/mapping_report/webodm_project_id`);

export const getImages = (report_id: number) => fetchJson<{ images: string[] }>(`/images/report/${report_id}`);
export const getImage = (image_id: number) => fetchJson<{ image: string }>(`/images/${image_id}`);
export const deleteImage = (image_id: number) => deleteRequest(`/images/${image_id}`);
export const getThermalMatrix = (image_id: number) => fetchJson<{ image_id: number; matrix: number[][]; min_temp: number; max_temp: number }>(`/images/${image_id}/thermal_matrix`);

export const startDetection = (report_id: number, processing_mode: string) => postJson<{ task_id: number}>(`/detections/r/${report_id}`, { processing_mode });
export const getDetectionStatus = (report_id: number) => fetchJson<{ report_id: number, status: string; progress: number; message?: string; error?: string }>(`/detections/r/${report_id}/status`);
export const getDetections = (report_id: number) => fetchJson<Image[]>(`/detections/r/${report_id}`);
export const updateDetection = (detection_id: number, data: Detection) => postJson<any>(`/detections/${detection_id}`, data, "PUT");

// WebODM integration

export const getWebODMAvailable = () => fetchJson<{ is_available: boolean, url: string }>("/odm/");
export const getWebODMTasks = (project_id: string) => fetchJson<any[]>(`/odm/projects/${project_id}/tasks`);
// POST: Start report processing
export const startReportProcessing = (
  reportId: number,
  settings: ProcessingSettings
): Promise<Report> =>
  postJson(`/reports/${reportId}/process`, settings);

// GET: Poll processing status
export const getReportProcessStatus = (
  reportId: number
): Promise<Report> =>
  fetchJson(`/reports/${reportId}/process/`);


//export api Url
export const getApiUrl = () => API_URL;