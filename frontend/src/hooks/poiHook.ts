import { useMutation } from "@tanstack/react-query";
import { sendDetectionToDrz } from "@/api";
import type { Geometry, Properties } from "@/types/detection";

type Vars = {
    geometry: Geometry;
    properties: Properties;
    /** Needed only when attach_image is set — the backend uses it to find the source frame. */
    detection_id?: number;
    /** Also upload the detection's image and link it to the POI that gets created. */
    attach_image?: boolean;
};

export function useSendDetectionToDrz() {
    return useMutation({
        mutationFn: ({ geometry, properties, detection_id, attach_image }: Vars) =>
            sendDetectionToDrz(geometry, properties, { detection_id, attach_image }),
    });
}
