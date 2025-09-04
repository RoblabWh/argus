import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { startDetection, getDetectionStatus, getDetections, updateDetection, deleteDetection } from "@/api";
import type { Detection } from "@/types/detection";
import type { Report } from "@/types/report";


export function useStartDetection() {
    return useMutation({
        mutationFn: ({ reportId, processingMode }: { reportId: number; processingMode: string }) =>
            startDetection(reportId, processingMode),
    });
}


export function useIsDetectionRunning(reportId: number) {
    return useQuery({
        queryKey: ["isDetectionRunning", reportId],
        queryFn: async () => {
            try {
                const status = await getDetectionStatus(reportId);
                return status.status !== ""//; && status.status !== "completed" && status.status !== "failed";
            } catch (err: any) {
                if (err.status === 404) {
                    return false; // no process running
                }
                throw err; // rethrow other errors
            }
        },
    });
}

export function useDetectionStatusPolling(reportId: number, enabled: boolean) {
    return useQuery({
        queryKey: ["detectionStatus", reportId],
        queryFn: () => getDetectionStatus(reportId),
        enabled,
        refetchInterval: enabled ? 2000 : false, // always poll if enabled
    });
}

export function useDetections(reportId: number) {
    return useQuery({
        queryKey: ["detections", reportId],
        queryFn: () => getDetections(reportId),
    });
}

export function useUpdateDetection(reportId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ detectionId, data }: { detectionId: number; data: Detection }) =>
            updateDetection(detectionId, data),
        onSuccess: () => {
            // Invalidate and refetch
            queryClient.invalidateQueries({ queryKey: ["detections", reportId] });
        },
    });
}

export function useDeleteDetection(reportId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (detectionId: number) => deleteDetection(detectionId),
        onSuccess: () => {
            // Invalidate and refetch
            console.log("successfully deleted detection");
        },
    });
}