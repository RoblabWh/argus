import { useMutation } from "@tanstack/react-query";
import { sendImageToDrz } from "@/api";
import type { ImageShareRequest } from "@/types/image";

type Vars = { imageId: number; body: ImageShareRequest };

/**
 * Share one mapping image with the DRZ/IAIS photo service.
 *
 * Mirrors useSendKeyframeToDrz, minus the cache invalidation: nothing about the send is
 * persisted on our side, so no query holds stale data afterwards.
 */
export function useSendImageToDrz() {
    return useMutation<{ success: boolean; message: string; photo_id: string | null }, Error, Vars>({
        mutationFn: ({ imageId, body }) => sendImageToDrz(imageId, body),
    });
}
