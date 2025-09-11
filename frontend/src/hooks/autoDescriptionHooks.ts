import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { startAutoDescription, getAutoDescription } from "@/api";


export function useStartAutoDescription(reportId: number) {
    return useMutation({
        mutationFn: () => startAutoDescription(reportId),
    });
}

export function useAutoDescriptionPolling(reportId: number, enabled: boolean) {
    return useQuery({
        queryKey: ["autoDescription", reportId],
        queryFn: () => getAutoDescription(reportId),
        enabled,
        refetchInterval: enabled ? 2000 : false,
    });
}