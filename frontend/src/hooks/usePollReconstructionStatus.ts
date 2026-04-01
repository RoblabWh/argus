import { useQuery } from "@tanstack/react-query";
import { getReconstructionStatus } from "@/api";

export interface ReconstructionStatusData {
  report_id: number;
  status: string;
  progress: number;
  message: string;
}

export function usePollReconstructionStatus(reportId: number, enabled: boolean) {
  return useQuery<ReconstructionStatusData>({
    queryKey: ["reconstruction-status", reportId],
    queryFn: () => getReconstructionStatus(reportId),
    enabled: !!reportId && enabled,
    refetchInterval: 2000,
    staleTime: 1500,
  });
}
