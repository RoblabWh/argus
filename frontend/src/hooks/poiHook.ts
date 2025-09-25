import { sendDetectionToDrz } from "@/api";
import type { Detection, Geometry, Properties } from "@/types/detection";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";

export function useSendDetectionToDrz() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ geometry, properties }: { geometry: Geometry; properties: Properties }) =>
            sendDetectionToDrz(geometry, properties),
        onSuccess: () => {
            // Invalidate and refetch
        },
    });
}