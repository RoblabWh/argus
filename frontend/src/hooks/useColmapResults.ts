import { useQuery } from "@tanstack/react-query";
import { getColmapResults, type ColmapResultsData } from "@/api";

// Fetches the point-cloud URLs of a finished COLMAP reconstruction. Enable it
// only once colmap-status reports has_reconstruction — a finished
// reconstruction never changes, so the result is cached indefinitely.
export function useColmapResults(reportId: number, enabled: boolean) {
  return useQuery<ColmapResultsData>({
    queryKey: ["colmap-results", reportId],
    queryFn: () => getColmapResults(reportId),
    enabled: !!reportId && enabled,
    staleTime: Infinity,
  });
}
