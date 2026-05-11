import { useMutation } from "@tanstack/react-query";
import { sendDetectionToDrz } from "@/api";
import type { Geometry, Properties } from "@/types/detection";

export function useSendDetectionToDrz() {
    return useMutation({
        mutationFn: ({ geometry, properties }: { geometry: Geometry; properties: Properties }) =>
            sendDetectionToDrz(geometry, properties),
    });
}
