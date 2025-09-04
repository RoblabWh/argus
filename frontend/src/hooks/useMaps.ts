// src/hooks/useMaps.ts
import { useQuery } from "@tanstack/react-query";
import { getMaps, getMapsSlim } from "@/api";

export const useMaps = (reportId: number, enabled = true) =>
  useQuery({
    queryKey: ["maps", reportId],
    queryFn: () => getMaps(reportId),
    enabled: !!reportId && enabled,
  });


  export const useMapsSlim = (reportId: number, enabled = true) =>
  useQuery({
    queryKey: ["mapsSlim", reportId],
    queryFn: () => getMapsSlim(reportId),
    enabled: !!reportId && enabled,
  });