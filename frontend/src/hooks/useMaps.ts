// src/hooks/useMaps.ts
import { useQuery } from "@tanstack/react-query";
import { getMaps } from "@/api";

export const useMaps = (reportId: number, enabled = true) =>
  useQuery({
    queryKey: ["maps", reportId],
    queryFn: () => getMaps(reportId),
    enabled: !!reportId && enabled,
  });
