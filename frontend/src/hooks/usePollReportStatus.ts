// src/hooks/usePollReportStatus.ts
import { useQuery } from "@tanstack/react-query";
import { getReportProcessStatus } from "@/api";
import type { Report } from "@/types/report";

export const usePollReportStatus = (reportId: number, enabled: boolean) =>
  useQuery<Report>({
    queryKey: ["report-process", reportId],
    queryFn: () => getReportProcessStatus(reportId),
    enabled: !!reportId && enabled,
    refetchInterval: 2000,
    staleTime: 1000,
  });

