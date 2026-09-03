import { useState, useEffect } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import type { ImageBasic } from "@/types/image"
import type { Detection } from "@/types/detection"
import { MANUAL_CLASS_OPTIONS } from "@/types/detection"
import { useCreateDetection } from "@/hooks/detectionHooks"
import { useMaps } from "@/hooks/useMaps"
import { computeDetectionGps } from "@/utils/coordinateUtils"

export type DraftBox = { x: number; y: number; w: number; h: number }

type DetectionCreatePopupProps = {
    reportId: number
    open: boolean
    onClose: () => void
    /** Bounding box the user drew, in source-image pixels */
    draft: DraftBox
    image: ImageBasic
    /** Called once the detection has been persisted */
    onCreated: () => void
}

/**
 * Confirmation step for a hand-drawn detection: pick the class, optionally mark it
 * verified, and persist. Mirrors DetectionEditPopup so the two read the same way.
 *
 * The GPS shown here is a client-side preview only — the server recomputes it from the
 * image's map footprint on create, and its version additionally honours the footprint's
 * src_px region, which computeDetectionGps does not.
 */
export function DetectionCreatePopup({ reportId, open, onClose, draft, image, onCreated }: DetectionCreatePopupProps) {
    const [currentClass, setCurrentClass] = useState<string>("other")
    const [verified, setVerified] = useState(false)
    const createDetection = useCreateDetection(reportId)
    const { data: maps } = useMaps(reportId)

    // Reset the form for each new box, so a previous pick doesn't leak into the next one.
    useEffect(() => {
        if (!open) return
        setCurrentClass("other")
        setVerified(false)
    }, [open, draft])

    const bbox: [number, number, number, number] = [
        Math.round(draft.x), Math.round(draft.y), Math.round(draft.w), Math.round(draft.h),
    ]

    const gpsPreview = computeDetectionGps(
        { bbox, image_id: image.id } as unknown as Detection,
        [image],
        maps,
    )

    const handleCreate = () => {
        if (createDetection.isPending) return
        createDetection.mutate(
            {
                image_id: image.id,
                class_name: currentClass,
                // Human-asserted, so it sits above every configured threshold and is
                // never silently filtered out of the gallery or the map.
                score: 1.0,
                bbox,
                manually_verified: verified,
            },
            {
                onSuccess: () => {
                    toast.success(`${currentClass} detection added`)
                    onCreated()
                    onClose()
                },
                onError: (err) => {
                    toast.error("Could not create detection", {
                        description: err instanceof Error ? err.message : String(err),
                    })
                },
            },
        )
    }

    return (
        <Dialog open={open} onOpenChange={(next) => { if (!next) onClose() }}>
            <DialogContent className="max-w-md rounded-2xl p-6">
                <DialogHeader>
                    <DialogTitle>Add Detection</DialogTitle>
                    <DialogDescription>
                        Record an object the detector missed. It will be marked as manually added
                        and kept when object detection is run again.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                    <div className="text-sm space-y-1">
                        <p><span className="font-semibold">Image:</span> {image.filename}</p>
                        <p>
                            <span className="font-semibold">Bounding box:</span>{" "}
                            x: {bbox[0]}, y: {bbox[1]}, w: {bbox[2]}, h: {bbox[3]}
                        </p>
                        <p>
                            <span className="font-semibold">Coordinate:</span>{" "}
                            {gpsPreview ? (
                                `${gpsPreview.lat.toFixed(6)}, ${gpsPreview.lon.toFixed(6)}`
                            ) : (
                                <span className="text-muted-foreground">
                                    not available — this image has no map footprint
                                </span>
                            )}
                        </p>
                    </div>

                    <div className="flex items-center space-x-2 w-full">
                        <Label>Class</Label>
                        <Select value={currentClass} onValueChange={setCurrentClass}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select class" />
                            </SelectTrigger>
                            <SelectContent>
                                {MANUAL_CLASS_OPTIONS.map((c) => (
                                    <SelectItem key={c} value={c}>
                                        {c}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="flex items-center space-x-2 w-full">
                        <Checkbox
                            id="create-verified"
                            checked={verified}
                            onCheckedChange={(checked) => setVerified(!!checked)}
                        />
                        <Label htmlFor="create-verified">Confirmed on site</Label>
                    </div>
                </div>

                <DialogFooter className="mt-6 flex justify-end space-x-2">
                    <Button variant="outline" onClick={onClose}>Cancel</Button>
                    <Button onClick={handleCreate} disabled={createDetection.isPending}>
                        {createDetection.isPending && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
                        Create
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
