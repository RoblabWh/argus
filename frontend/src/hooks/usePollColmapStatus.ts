import { useQuery } from "@tanstack/react-query";
import { getColmapStatus, type ColmapStatusData } from "@/api";

// `suspend` pauses the interval while SSE is delivering the same data into
// this query's cache (see useReportEvents); polling resumes if SSE drops.
export function usePollColmapStatus(reportId: number, enabled: boolean, suspend = false) {
  return useQuery<ColmapStatusData>({
    queryKey: ["colmap-status", reportId],
    queryFn: () => getColmapStatus(reportId),
    enabled: !!reportId && enabled,
    // COLMAP is dispatched *after* mapping finishes, so at mount the status is usually
    // "none". Keep polling on none/queued/running and stop only on a terminal status, so the
    // indicator catches the job once it's queued without needing a page reload.
    refetchInterval: (query) => {
      if (suspend) return false;
      const s = query.state.data?.status;
      return s === "completed" || s === "error" ? false : 2000;
    },
    staleTime: 1500,
  });
}
