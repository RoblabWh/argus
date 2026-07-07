import { useQuery } from "@tanstack/react-query";
import { getReconstructionStatus } from "@/api";

export interface ReconstructionStatusData {
  report_id: number;
  status: string;
  progress: number;
  message: string;
}

// `suspend` pauses the interval while SSE is delivering the same data into
// this query's cache (see useReportEvents); polling resumes if SSE drops.
export function usePollReconstructionStatus(reportId: number, enabled: boolean, suspend = false) {
  return useQuery<ReconstructionStatusData>({
    queryKey: ["reconstruction-status", reportId],
    queryFn: () => getReconstructionStatus(reportId),
    enabled: !!reportId && enabled,
    refetchInterval: suspend ? false : 2000,
    staleTime: 1500,
  });
}
