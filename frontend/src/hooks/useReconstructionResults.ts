import { useQuery } from "@tanstack/react-query";
import { getReconstructionResults } from "@/api";
import type { ReconstructionResults } from "@/types/reconstruction";

export function useReconstructionResults(reportId: number, enabled: boolean) {
  return useQuery<ReconstructionResults>({
    queryKey: ["reconstruction-results", reportId],
    queryFn: () => getReconstructionResults(reportId),
    enabled: !!reportId && enabled,
    staleTime: Infinity, // Results are immutable once produced
  });
}
