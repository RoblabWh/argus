// src/api/groups.ts
import type { Group } from "@/types/group";
import type { Report } from "@/types/report";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function fetchJson<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${API_URL}${endpoint}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${endpoint}: ${res.status}`);
  }
  return res.json();
}

export const getGroups = () => fetchJson<Group[]>("/groups/");
export const getGroup = (id: number) => fetchJson<Group>(`/groups/${id}`);
export const getGroupReports = (id: number) => fetchJson<Report[]>(`/groups/${id}/reports`);