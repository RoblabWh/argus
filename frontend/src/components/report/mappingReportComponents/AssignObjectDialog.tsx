import { useEffect, useMemo, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Plus, Ban } from "lucide-react";
import { toast } from "sonner";
import { getApiUrl } from "@/api";
import type { Detection } from "@/types/detection";
import type { ImageBasic } from "@/types/image";
import { useDetections, useUpdateUniqueObject } from "@/hooks/detectionHooks";
import { useImages } from "@/hooks/imageHooks";
import { groupDetectionsByObject, getNextObjectId } from "@/utils/detectionUtils";
import { BBoxCrop } from "@/components/report/mappingReportComponents/slideshow/BBoxCrop";

type AssignObjectDialogProps = {
    reportId: number;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    detection: Detection | null;
};

/** Convert a detection's bbox (stored as a numeric-indexed record) to [x, y, w, h] px. */
function bboxOf(det: Detection): [number, number, number, number] {
    const b = det.bbox as unknown as number[];
    return [Number(b[0]), Number(b[1]), Number(b[2]), Number(b[3])];
}

/**
 * Reusable overlay for manually (re)assigning a detection's re-identification cluster
 * (`unique_object_id`). Opened from the map popup and the gallery crop tiles. Lets the user
 * pick an existing object from a visual list, create a New object, or Unassign.
 */
export function AssignObjectDialog({ reportId, open, onOpenChange, detection }: AssignObjectDialogProps) {
    const { data: detections } = useDetections(reportId);
    const { data: images } = useImages(reportId);
    const updateUniqueObject = useUpdateUniqueObject(reportId);
    const apiUrl = getApiUrl();

    const current = detection?.unique_object_id ?? null;
    // target: a numeric object id, null (unassign) or "new" (create next id)
    const [target, setTarget] = useState<number | null | "new">(current);

    useEffect(() => {
        setTarget(detection?.unique_object_id ?? null);
    }, [detection]);

    const imageById = useMemo(() => {
        const m = new Map<number, ImageBasic>();
        for (const img of images ?? []) m.set(img.id, img);
        return m;
    }, [images]);

    // Existing objects, sorted same-class-first then by id, for the picker grid
    const objectEntries = useMemo(() => {
        const { clusters } = groupDetectionsByObject(detections);
        const cls = detection?.class_name;
        return Array.from(clusters.entries()).sort((a, b) => {
            const aSame = a[1][0].class_name === cls ? 0 : 1;
            const bSame = b[1][0].class_name === cls ? 0 : 1;
            return aSame - bSame || a[0] - b[0];
        });
    }, [detections, detection]);

    const renderCrop = (det: Detection, size: number) => {
        const img = imageById.get(det.image_id);
        if (!img) return <div style={{ width: size, height: size }} className="rounded-sm bg-muted" />;
        return (
            <BBoxCrop
                imageUrl={`${apiUrl}/${img.url}`}
                imageWidth={img.width}
                imageHeight={img.height}
                bbox={bboxOf(det)}
                thumbSize={size}
                alt={img.filename}
            />
        );
    };

    const unchanged = target === current;

    const handleAssign = () => {
        if (!detection) return;
        const uid = target === "new" ? getNextObjectId(detections) : target;
        updateUniqueObject.mutate(
            { uniqueObjectId: uid, detectionIds: [detection.id] },
            {
                onSuccess: () => {
                    toast.success(
                        uid == null ? "Detection unassigned" : `Assigned to object #${uid}`
                    );
                    onOpenChange(false);
                },
                onError: () => toast.error("Failed to update assignment"),
            }
        );
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg rounded-2xl">
                <DialogHeader>
                    <DialogTitle>Assign detection to object</DialogTitle>
                    <DialogDescription>
                        Group this detection with others of the same physical object, or unassign it.
                    </DialogDescription>
                </DialogHeader>

                {detection && (
                    <div className="space-y-4">
                        {/* Edited detection */}
                        <div className="flex items-center gap-3 rounded-md border p-2">
                            {renderCrop(detection, 64)}
                            <div className="text-sm">
                                <div className="font-semibold capitalize">{detection.class_name}</div>
                                <div className="text-muted-foreground">Score: {(detection.score * 100).toFixed(0)}%</div>
                                <div className="text-muted-foreground">
                                    Currently: {current == null ? "unassigned" : `Object #${current}`}
                                </div>
                            </div>
                        </div>

                        {/* Quick actions */}
                        <div className="flex items-center gap-2">
                            <Button
                                type="button"
                                variant={target === "new" ? "default" : "outline"}
                                size="sm"
                                onClick={() => setTarget("new")}
                            >
                                <Plus className="h-4 w-4 mr-1" /> New object
                            </Button>
                            <Button
                                type="button"
                                variant={target === null ? "default" : "outline"}
                                size="sm"
                                onClick={() => setTarget(null)}
                            >
                                <Ban className="h-4 w-4 mr-1" /> Unassign
                            </Button>
                        </div>

                        {/* Existing objects */}
                        <div>
                            <div className="text-xs font-semibold text-muted-foreground mb-2">
                                {objectEntries.length ? "Assign to existing object" : "No existing objects yet"}
                            </div>
                            <div className="max-h-64 overflow-auto grid grid-cols-[repeat(auto-fill,minmax(88px,1fr))] gap-2 justify-items-center">
                                {objectEntries.map(([uid, members]) => {
                                    const selected = target === uid;
                                    const isCurrent = uid === current;
                                    return (
                                        <button
                                            key={uid}
                                            type="button"
                                            onClick={() => setTarget(uid)}
                                            className={`flex flex-col items-center gap-1 rounded-md p-1 border transition
                                                ${selected ? "border-primary ring-2 ring-primary/50" : "border-input hover:bg-accent"}`}
                                        >
                                            {renderCrop(members[0], 72)}
                                            <span className="text-[10px] leading-tight text-center">
                                                #{uid} · {members[0].class_name} · {members.length}
                                                {isCurrent ? " ★" : ""}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                )}

                <DialogFooter className="mt-2">
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button onClick={handleAssign} disabled={unchanged || updateUniqueObject.isPending}>
                        {target === "new" ? "Create & assign" : target === null ? "Unassign" : "Assign"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
