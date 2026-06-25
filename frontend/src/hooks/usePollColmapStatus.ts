import { useQuery } from "@tanstack/react-query";
import { getColmapStatus, type ColmapStatusData } from "@/api";

export function usePollColmapStatus(reportId: number, enabled: boolean) {
  return useQuery<ColmapStatusData>({
    queryKey: ["colmap-status", reportId],
    queryFn: () => getColmapStatus(reportId),
    enabled: !!reportId && enabled,
    // COLMAP is dispatched *after* mapping finishes, so at mount the status is usually
    // "none". Keep polling on none/queued/running and stop only on a terminal status, so the
    // indicator catches the job once it's queued without needing a page reload.
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "completed" || s === "error" ? false : 2000;
    },
    staleTime: 1500,
  });
}
