import { useEffect, useMemo, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { CoordinatePickerMap, type Coordinate } from "@/components/shared/CoordinatePickerMap";
import { LockButton } from "@/components/shared/LockedField";
import { useSendImageToDrz } from "@/hooks/useSendImageToDrz";
import type { ImageBasic } from "@/types/image";
import { toast } from "sonner";
import { Loader2, Send, Share2 } from "lucide-react";

interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    image: ImageBasic | null;
    reportTitle?: string;
    reportId: number;
}

/**
 * Share a single mapping image with the DRZ/IAIS photo service.
 *
 * Adapted from KeyframeSharePopup, which does the same for 360° panoramas. The one real
 * difference is the coordinate: a SLAM keyframe has none, so picking one on the map is
 * mandatory there, whereas a mapping image normally carries EXIF GPS and the picker is only
 * a fallback (and a way to correct a bad fix).
 */
export function ImageSharePopup({ open, onOpenChange, image, reportTitle, reportId }: Props) {
    const [coord, setCoord] = useState<Coordinate | null>(null);
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [direction, setDirection] = useState("");
    const [errorText, setErrorText] = useState("");
    // Locked whenever the image brought its own coordinate, so a stray click cannot quietly
    // replace a good EXIF fix. Unlocking is the deliberate act of overriding it.
    const [posLocked, setPosLocked] = useState(true);

    const { mutateAsync: sendToDrz, isPending: isSending } = useSendImageToDrz();

    const gps = image?.coord?.gps;
    const defaultName = useMemo(
        () => `${reportTitle || `Report ${reportId}`} — ${image?.filename ?? ""}`.trim(),
        [reportTitle, reportId, image?.filename],
    );

    // Re-seed every time the dialog opens or the image changes, so a previous image's
    // values can never be sent against the current one.
    useEffect(() => {
        if (!open) return;
        setErrorText("");
        setCoord(gps ? { lat: gps.lat, lon: gps.lon } : null);
        setPosLocked(Boolean(gps));
        setName(defaultName);
        setDescription("");
        // The photo service's `direction` is the compass heading the shot was taken along,
        // which is exactly the camera yaw recorded during preprocessing.
        const yaw = image?.mapping_data?.cam_yaw;
        setDirection(yaw === undefined || yaw === null ? "" : String(Math.round(yaw)));
    }, [open, image?.id]);

    const handleOpenChange = (next: boolean) => {
        if (isSending) return;
        onOpenChange(next);
    };

    const handleSend = async () => {
        if (!image || !coord || !name.trim()) return;
        setErrorText("");
        const parsedDirection = direction.trim() === "" ? null : Number(direction);
        try {
            const resp = await sendToDrz({
                imageId: image.id,
                body: {
                    lat: coord.lat,
                    lon: coord.lon,
                    name: name.trim(),
                    description: description.trim() || null,
                    direction: Number.isFinite(parsedDirection as number) ? parsedDirection : null,
                },
            });
            if (resp.success) {
                toast.success("Image sent to the DRZ system");
                onOpenChange(false);
            } else {
                // The backend answers 200 with success=false for a remote rejection, so the
                // partner system's own message reaches the operator instead of a generic error.
                setErrorText(resp.message || "Upload failed.");
            }
        } catch (err) {
            setErrorText(err instanceof Error ? err.message : "Upload failed.");
        }
    };

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent
                className="sm:max-w-xl rounded-2xl p-6 max-h-[90vh] overflow-y-auto"
                onPointerDownOutside={(e) => { if (isSending) e.preventDefault(); }}
                onEscapeKeyDown={(e) => { if (isSending) e.preventDefault(); }}
            >
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Share2 className="size-4" /> Share Image
                    </DialogTitle>
                </DialogHeader>

                <div className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                        Uploads {image?.filename} to the DRZ photo service as a standalone photo,
                        not attached to any point of interest.
                    </p>

                    <div className="space-y-2">
                        <Label htmlFor="image-share-name">Name</Label>
                        <Input
                            id="image-share-name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="image-share-desc">Description (optional)</Label>
                        <Textarea
                            id="image-share-desc"
                            rows={2}
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="image-share-dir">Camera direction (optional, degrees)</Label>
                        <Input
                            id="image-share-dir"
                            inputMode="numeric"
                            placeholder="0 = north"
                            value={direction}
                            onChange={(e) => setDirection(e.target.value)}
                        />
                    </div>

                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <Label>Position</Label>
                            {gps && (
                                <LockButton
                                    locked={posLocked}
                                    label="position"
                                    onToggle={() => {
                                        // Re-locking restores the coordinate read from the image,
                                        // so the lock doubles as an undo for an accidental edit.
                                        if (!posLocked) setCoord({ lat: gps.lat, lon: gps.lon });
                                        setPosLocked((l) => !l);
                                    }}
                                />
                            )}
                        </div>
                        <p className="text-xs text-muted-foreground">
                            {!gps
                                ? "This image has no GPS in its metadata — pick the position on the map."
                                : posLocked
                                    ? "Position read from the image. Unlock to correct it."
                                    : "Unlocked — click the map, drag the marker, or type a coordinate. Re-lock to restore the original."}
                        </p>
                        <CoordinatePickerMap
                            value={coord}
                            onChange={setCoord}
                            defaultCenter={gps ? { lat: gps.lat, lon: gps.lon } : undefined}
                            visible={open}
                            locked={posLocked}
                        />
                    </div>

                    {errorText && (
                        <p className="text-xs text-red-600 break-words">{errorText}</p>
                    )}

                    <div className="flex justify-end gap-2 pt-2">
                        <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={isSending}>
                            Cancel
                        </Button>
                        <Button onClick={handleSend} disabled={!coord || !name.trim() || isSending}>
                            {isSending
                                ? <><Loader2 className="h-4 w-4 animate-spin" /> Sending…</>
                                : <><Send className="h-4 w-4" /> Send to DRZ</>}
                        </Button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
