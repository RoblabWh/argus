import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { startAutoDescription, getAutoDescription } from "@/api";


export function useStartAutoDescription(reportId: number) {
    return useMutation({
        mutationFn: () => startAutoDescription(reportId),
    });
}

// `suspend` pauses the interval while SSE is delivering the same data into
// this query's cache (see useReportEvents); polling resumes if SSE drops.
export function useAutoDescriptionPolling(reportId: number, enabled: boolean, suspend = false) {
    return useQuery({
        queryKey: ["autoDescription", reportId],
        queryFn: () => getAutoDescription(reportId),
        enabled,
        refetchInterval: enabled && !suspend ? 2000 : false,
    });
}