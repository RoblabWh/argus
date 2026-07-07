// src/hooks/usePollReportStatus.ts
import { useQuery } from "@tanstack/react-query";
import { getReportProcessStatus } from "@/api";
import type { Report } from "@/types/report";

// `suspend` pauses the interval while SSE is delivering the same data into
// this query's cache (see useReportEvents); polling resumes if SSE drops.
export const usePollReportStatus = (reportId: number, enabled: boolean, suspend = false) =>
  useQuery<Report>({
    queryKey: ["report-process", reportId],
    queryFn: () => getReportProcessStatus(reportId),
    enabled: !!reportId && enabled,
    refetchInterval: suspend ? false : 1250,
    staleTime: 1000,
  });
