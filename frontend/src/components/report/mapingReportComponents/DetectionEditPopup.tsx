import React, { useState, useEffect } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import type { Detection } from "@/types/detection"
import { useUpdateDetection } from "@/hooks/detectionHooks"

type DetectionEditPopupProps = {
    reportId: number
    open: boolean
    onClose: () => void
    detection: Detection
    onSave: (updated: Detection) => void
    timestamp: string
}

const CLASS_OPTIONS = ["fire", "human", "vehicle"]

export function DetectionEditPopup({ open, onClose, detection, onSave, timestamp, reportId }: DetectionEditPopupProps) {
    const [currentClass, setCurrentClass] = useState(detection.class_name)
    const [verified, setVerified] = useState(detection.manually_verified ?? false)
    const updateDetectionMutation = useUpdateDetection(reportId)
    let datestring = new Date(timestamp).toLocaleString()

    // Reset state when detection changes
    useEffect(() => {
        setCurrentClass(detection.class_name)
        setVerified(detection.manually_verified ?? false)
    }, [detection])

    const handleSave = () => {
        onSave({
            ...detection,
            class_name: currentClass,
            manually_verified: verified,
        })
        updateDetectionMutation.mutate({
            detectionId: detection.id,
            data: {
                ...detection,
                class_name: currentClass,
                manually_verified: verified,
            },
        })

        onClose()
    }

    return (
        <Dialog open={open} onOpenChange={onClose}>
            <DialogContent className="max-w-md rounded-2xl p-6">
                <DialogHeader>
                    <DialogTitle>Edit Detection</DialogTitle>
                </DialogHeader>

                <div className="space-y-4">
                    {/* Class selection */}
                    <div className="space-y-2">
                        <div className="text-sm space-y-1">
                            <p><span className="font-semibold">Class:</span> {detection.class_name}</p>
                            <p><span className="font-semibold">ID:</span> {detection.id}</p>
                            <p><span className="font-semibold">Score:</span> {detection.score.toFixed(2)}</p>
                            {detection.coord && (
                                <p>
                                    <span className="font-semibold">Coordinate:</span> x: {detection.coord.x}, y: {detection.coord.y}
                                </p>
                            )}
                            <p><span className="font-semibold">Timestamp:</span> {datestring}</p>
                        </div>
                    </div>

                    <div className="flex items-center space-x-2 w-full">
                        <Label>Class</Label>
                        <Select value={currentClass} onValueChange={setCurrentClass}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select class" />
                            </SelectTrigger>
                            <SelectContent>
                                {CLASS_OPTIONS.map((c) => (
                                    <SelectItem key={c} value={c}>
                                        {c}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Verified toggle */}
                    <div className="flex items-center space-x-2 w-full">
                        <Checkbox
                            id="verified"
                            checked={verified}
                            onCheckedChange={(checked) => setVerified(!!checked)}
                        />
                        <Label htmlFor="verified">Manually verified</Label>
                    </div>
                </div>

                <DialogFooter className="mt-6 flex justify-end space-x-2">
                    <Button variant="outline" onClick={onClose}>Cancel</Button>
                    <Button onClick={handleSave}>Save Changes</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
