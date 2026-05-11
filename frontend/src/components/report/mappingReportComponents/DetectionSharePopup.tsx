import { useState, useEffect } from "react"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"
import { Loader2, X, Info } from "lucide-react"
import { toast } from "sonner"
import { ComboButton } from "@/components/ComboButton"
import type { Geometry, Properties, Detection } from "@/types/detection"
import { useSendDetectionToDrz } from "@/hooks/poiHook"

type DrzError = { message: string; detail: string | null }



type DetectionSharePopupProps = {
    open: boolean
    onClose: () => void
    detection: Detection
    timestamp: string
    drzBackendApi?: string
}

function shareAsEmail(type: string, detail: string, subtype: string, name: string, description: string, coordinate: string, author: string, timestamp: string) {
    const emailBody = `
    The following object detection has been made:
        Type: ${type}
        Detail: ${detail}
        Subtype: ${subtype}
        Name: ${name}
        Description: ${description}
        Coordinate: ${coordinate}
        Author: ${author}
        Image Timestamp: ${timestamp}
    `;
    // Send email using your preferred email service
    const subject = `ARGUS Object Detection: ${type}`;
    const mailtoLink = `mailto:?to=&body=${encodeURIComponent(emailBody)}&subject=${encodeURIComponent(subject)}`;
    window.open(mailtoLink, '_blank');
    console.log("share as email")
}



export function DetectionSharePopup({
    open,
    onClose,
    detection,
    timestamp,
    drzBackendApi,
}: DetectionSharePopupProps) {
    const [sendOption, setSendOption] = useState<"email" | "gps" | "drz">("email")
    const { mutateAsync: sendToDrz, isPending: isSendingDrz } = useSendDetectionToDrz()
    // form states
    const [name, setName] = useState("")
    const [description, setDescription] = useState("")
    const [author, setAuthor] = useState("")
    const [detail, setDetail] = useState<string>("")
    const [subtype, setSubtype] = useState<string>("")
    const [drzError, setDrzError] = useState<DrzError | null>(null)

    // Pre-fill coordinate & type detail based on class
    useEffect(() => {
        const cls = detection.class_name?.toLowerCase() ?? ""
        if (cls.includes("human")) {
            setDetail("-1")
            setSubtype("Person")
        } else if (cls.includes("vehicle")) {
            setDetail("-1")
            setSubtype("Land vehicle (car, truck, trailer)")
        } else if (cls.includes("fire")) {
            setDetail("7")
            setSubtype("Fire (medium)")
        }
        if (description === "") {
            setDescription(`${cls.charAt(0).toUpperCase() + cls.slice(1)} detected by AI with score ${detection.score.toFixed(2)}`)
        }
        if (author === "") {
            setAuthor("Argus AI Detection");
        }
    }, [detection])

    const handleSend = async () => {
        const payload = {
            id: detection.id,
            type: detection.class_name,
            detail,
            subtype,
            name,
            description,
            coordinate: detection.coord,
            author,
            timestamp,
        }

        if (sendOption === "email") {
            shareAsEmail(
                payload.type,
                payload.detail,
                payload.subtype,
                payload.name,
                payload.description,
                JSON.stringify(payload.coordinate),
                payload.author,
                payload.timestamp,
            )
            handleClose()
            return
        }
        if (sendOption === "gps") {
            console.log("Download GPS POI", payload)
            handleClose()
            return
        }
        // sendOption === "drz"
        if (!drzBackendApi || !payload.coordinate) return
        if (isSendingDrz) return

        setDrzError(null)
        const geometry: Geometry = {
            type: "Point",
            coordinates: [payload.coordinate.gps.lon, payload.coordinate.gps.lat],
        }
        const properties: Properties = {
            type: payload.detail,
            subtype: payload.subtype,
            detection: 0,
            name: payload.name,
            description: payload.description,
            datetime: payload.timestamp,
        }

        try {
            const resp = await sendToDrz({ geometry, properties })
            if (resp.error) {
                setDrzError({
                    message: resp.message || "Failed to send to DRZ.",
                    detail: resp.error,
                })
                return
            }
            toast.success(resp.message || "Detection sent to DRZ.")
            handleClose()
        } catch (e) {
            setDrzError({
                message: "Could not reach DRZ backend.",
                detail: e instanceof Error ? e.message : String(e),
            })
        }
    }

    const handleClose = () => {
        //reset form
        setName("")
        setDescription("")
        // setAuthor("")
        setDetail("")
        setSubtype("")
        setDrzError(null)
        onClose()
    }

    // Dismiss a stale error whenever the user edits the form or switches send option.
    useEffect(() => {
        setDrzError(null)
    }, [name, description, author, detail, subtype, sendOption])

    const cls = detection.class_name?.toLowerCase() ?? ""
    const dateString = new Date(timestamp).toLocaleString()

    return (
        <Dialog open={open} onOpenChange={(o) => { if (!o && !isSendingDrz) handleClose() }}>
            <DialogContent
                className="max-w-xl rounded-2xl p-6"
                onPointerDownOutside={(e) => { if (isSendingDrz) e.preventDefault() }}
                onEscapeKeyDown={(e) => { if (isSendingDrz) e.preventDefault() }}
            >
                <DialogHeader>
                    <DialogTitle>Share Object Detection</DialogTitle>
                </DialogHeader>

                <form className="space-y-4 mt-2">
                    <div className="flex items-center space-x-1 mb-2">
                        <div className="text-md font-semibold">
                            {detection.class_name.charAt(0).toUpperCase() + detection.class_name.slice(1)}
                        </div>
                        <div className="text-md italic">
                            (Score {detection.score.toFixed(2)})
                        </div>
                    </div>
                    {/* Type & basic info */}
                    <div className="space-y-1 grid text-sm">

                        {detection.coord && (
                            <p>
                                <span className="font-semibold">Coordinate:</span> lat: {detection.coord.gps.lat}, lon: {detection.coord.gps.lon}
                            </p>
                        )}
                        <p>
                            <span className="font-semibold">Timestamp:</span> {dateString}
                        </p>
                    </div>

                    {/* Dynamic details per class */}
                    {cls.includes("human") && (
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <Label>Organizational affiliation</Label>
                                <Select value={detail} onValueChange={setDetail}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        {[
                                            ["1", "Fire department"],
                                            ["2", "USAR"],
                                            ["3", "EMS"],
                                            ["4", "Police"],
                                            ["5", "Army"],
                                            ["6", "Other"],
                                            ["9", "Command"],
                                            ["10", "People"],
                                            ["-1", "All/Unspecified"],
                                        ].map(([v, l]) => (
                                            <SelectItem key={v} value={v}>{l}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>Subtype</Label>
                                <Select value={subtype} onValueChange={setSubtype}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        {[
                                            "Person",
                                            "Person in distress (trapped/buried)",
                                            "Person injured",
                                            "Person dead",
                                            "Missing person",
                                            "Buried person",
                                            "Presumably buried person",
                                        ].map((l) => (
                                            <SelectItem key={l} value={l}>{l}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    )}

                    {cls.includes("vehicle") && (
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <Label>Organizational affiliation</Label>
                                <Select value={detail} onValueChange={setDetail}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        {[
                                            ["1", "Fire department"],
                                            ["2", "USAR"],
                                            ["3", "EMS"],
                                            ["4", "Police"],
                                            ["5", "Army"],
                                            ["6", "Other"],
                                            ["9", "Command"],
                                            ["10", "People"],
                                            ["-1", "All/Unspecified"],
                                        ].map(([v, l]) => (
                                            <SelectItem key={v} value={v}>{l}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>Subtype</Label>
                                <Select value={subtype} onValueChange={setSubtype}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        {[
                                            "Land vehicle (car, truck, trailer)",
                                            "Rail vehicle (locomotive, wagon)",
                                            "Water vehicle (boat, ship)",
                                            "Air vehicle (airplane, helicopter)",
                                            "Helicopter",
                                        ].map((l) => (
                                            <SelectItem key={l} value={l}>{l}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    )}

                    {cls.includes("fire") && (
                        <div className="space-y-4">
                            {/* hidden mainType = 7 */}
                            <input type="hidden" value="7" />
                            <div className="space-y-2">
                                <Label>Subtype</Label>
                                <Select value={subtype} onValueChange={setSubtype}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        {["Fire (small)", "Fire (medium)", "Fire (large)"].map((l) => (
                                            <SelectItem key={l} value={l}>{l}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    )}

                    {/* Common fields */}
                    <div className="space-y-2">
                        <Label>Name</Label>
                        <Input value={name} onChange={(e) => setName(e.target.value)} required />
                    </div>

                    <div className="space-y-2">
                        <Label>Description</Label>
                        <Textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            required
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Send by</Label>
                        <Input value={author} onChange={(e) => setAuthor(e.target.value)} required />
                    </div>

                    {drzError && (
                        <div className="inline-flex items-center gap-1.5 self-start rounded-md bg-red-500/10 text-red-700 dark:text-red-400 px-2 py-1 text-sm">
                            <X className="h-4 w-4 shrink-0" />
                            <span>{drzError.message}</span>
                            {drzError.detail && (
                                <Popover>
                                    <PopoverTrigger asChild>
                                        <button
                                            type="button"
                                            aria-label="Show error detail"
                                            className="ml-0.5 inline-flex items-center hover:opacity-80"
                                        >
                                            <Info className="h-3.5 w-3.5" />
                                        </button>
                                    </PopoverTrigger>
                                    <PopoverContent className="w-96 max-h-80 overflow-auto">
                                        <div className="text-xs font-mono whitespace-pre-wrap break-words">
                                            {drzError.detail}
                                        </div>
                                    </PopoverContent>
                                </Popover>
                            )}
                        </div>
                    )}

                    <DialogFooter className="pt-4 flex justify-between">
                        <Button variant="outline" onClick={handleClose} disabled={isSendingDrz}>Cancel</Button>
                        <ComboButton
                            value={sendOption}
                            options={[
                                { key: "email", label: "Send via Email" },
                                { key: "gps", label: "Download GPS POI" },
                                ...(drzBackendApi ? [{ key: "drz", label: "Send to DRZ System" }] : []),
                            ]}
                            onChange={(key) => setSendOption(key as typeof sendOption)}
                            onAction={handleSend}
                            disabled={isSendingDrz}
                        >
                            {isSendingDrz && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
                        </ComboButton>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}
