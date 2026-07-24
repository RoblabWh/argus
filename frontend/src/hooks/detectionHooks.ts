import { keepPreviousData, useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { startDetection, getDetectionStatus, getDetections, getFireMap, updateDetection, deleteDetection, updateDetectionBatch, updateDetectionUniqueObject, getNewDetections } from "@/api";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
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
                // Terminal Redis state survives restarts by design — only a
                // genuinely active run may arm the progress-bar polling.
                const s = (status.status || "").toLowerCase();
                return s !== "" && !["finished", "error", "failed"].includes(s);
            } catch (err: any) {
                if (err.status === 404) {
                    return false; // no process running
                }
                throw err; // rethrow other errors
            }
        },
    });
}

// `suspend` pauses the interval while SSE is delivering the same data into
// this query's cache (see useReportEvents); polling resumes if SSE drops.
export function useDetectionStatusPolling(reportId: number, enabled: boolean, suspend = false) {
    return useQuery({
        queryKey: ["detectionStatus", reportId],
        queryFn: () => getDetectionStatus(reportId),
        enabled,
        refetchInterval: enabled && !suspend ? 2000 : false, // poll if enabled and SSE is down
    });
}

export function useDetections(reportId: number) {
    return useQuery({
        queryKey: ["detections", reportId],
        queryFn: () => getDetections(reportId),
    });
}

// Server-generated fire overlay (GeoJSON confidence bands + region->image
// attribution). Only fetched while the map's fire layer is switched on;
// invalidated alongside ["detections"] when new detections arrive. The fire
// threshold is debounced so arrow-clicking the number field doesn't fire a
// request per step; keepPreviousData avoids flicker while recomputing.
export function useFireMap(reportId: number, enabled: boolean, fireThreshold?: number) {
    const debounced = useDebouncedValue(fireThreshold, 400);
    return useQuery({
        queryKey: ["fireMap", reportId, debounced ?? null],
        queryFn: () => getFireMap(reportId, debounced),
        enabled,
        placeholderData: keepPreviousData,
    });
}

export function useFetchNewDetections(reportId: number) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async () => {
            const cached = queryClient.getQueryData<Detection[]>(["detections", reportId]) ?? [];
            const knownIds = cached.map(d => d.id);

            const newOnes = await getNewDetections(reportId, knownIds);

            // merge into cache
            const merged = [...cached, ...newOnes];
            queryClient.setQueryData(["detections", reportId], merged);

            return merged;
        }
    });
}

export function useUpdateDetection(reportId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ detectionId, data }: { detectionId: number; data: Detection }) =>
            updateDetection(detectionId, data),
        onSuccess: () => {
            // Invalidate and refetch; the fire overlay is derived from the
            // detections table, so it must follow edits too.
            queryClient.invalidateQueries({ queryKey: ["detections", reportId] });
            queryClient.invalidateQueries({ queryKey: ["fireMap", reportId] });
        },
    });
}

export function useDeleteDetection(reportId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (detectionId: number) => deleteDetection(detectionId),
        onSuccess: () => {
            // Re-cluster map + gallery once a detection is removed; the fire
            // overlay is derived from the detections table, so it follows too.
            queryClient.invalidateQueries({ queryKey: ["detections", reportId] });
            queryClient.invalidateQueries({ queryKey: ["fireMap", reportId] });
        },
    });
}

export function useUpdateUniqueObject(reportId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ uniqueObjectId, detectionIds }: { uniqueObjectId: number | null; detectionIds: number[] }) =>
            updateDetectionUniqueObject(reportId, uniqueObjectId, detectionIds),
        onSuccess: () => {
            // Re-cluster map + gallery once the assignment changes
            queryClient.invalidateQueries({ queryKey: ["detections", reportId] });
        },
    });
}

export function useUpdateDetectionBatch(reportId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: Detection[]) =>
            updateDetectionBatch(reportId, data),
        onSuccess: () => {
            // Invalidate and refetch
            queryClient.invalidateQueries({ queryKey: ["detections", reportId] });
        },
    });
}