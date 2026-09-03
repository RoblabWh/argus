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
import { Checkbox } from "@/components/ui/checkbox"
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"
import { Loader2, X, Info, Check } from "lucide-react"
import { toast } from "sonner"
import { ComboButton } from "@/components/ComboButton"
import type { Geometry, Properties, Detection } from "@/types/detection"
import { useSendDetectionToDrz } from "@/hooks/poiHook"
import {
    DRZ_SUBTYPE_GROUPS,
    DRZ_MAIN_TYPES,
    DRZ_DANGER_LEVELS,
    drzDefaultsForClass,
    drzGroupRules,
} from "@/types/drz"

type DrzError = { message: string; detail: string | null }



type DetectionSharePopupProps = {
    open: boolean
    onClose: () => void
    detection: Detection
    timestamp: string
    /** Whether a DRZ backend is configured in Settings; gates the "Send to DRZ System" option. */
    drzConfigured?: boolean
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
    drzConfigured = false,
}: DetectionSharePopupProps) {
    const [sendOption, setSendOption] = useState<"email" | "gps" | "drz">("email")
    const { mutateAsync: sendToDrz, isPending: isSendingDrz } = useSendDetectionToDrz()
    // form states
    const [name, setName] = useState("")
    const [description, setDescription] = useState("")
    const [author, setAuthor] = useState("")
    const [detail, setDetail] = useState<string>("")
    const [group, setGroup] = useState<string>("")
    const [subtype, setSubtype] = useState<string>("")
    const [dangerLevel, setDangerLevel] = useState<string>("false")
    const [attachImage, setAttachImage] = useState(false)
    const [drzError, setDrzError] = useState<DrzError | null>(null)
    // Brief post-success state: the button confirms in place before the dialog closes.
    const [drzSent, setDrzSent] = useState(false)

    // Pre-fill coordinate & type detail based on class
    useEffect(() => {
        const cls = detection.class_name?.toLowerCase() ?? ""
        // Category/subtype/affiliation come from one catalog now (types/drz.ts), transcribed
        // from the DRZ OpenAPI spec. "other" prefills nothing but the affiliation — only the
        // operator knows what they marked, and DRZ validates the subtype against its enum.
        const defaults = drzDefaultsForClass(detection.class_name)
        setDetail(defaults.mainType)
        setGroup(defaults.group)
        setSubtype(defaults.subtype)
        if (description === "") {
            setDescription(
                detection.manually_created
                    ? `${cls.charAt(0).toUpperCase() + cls.slice(1)} marked manually in the image`
                    : `${cls.charAt(0).toUpperCase() + cls.slice(1)} detected by AI with score ${detection.score.toFixed(2)}`
            )
        }
        if (author === "") {
            setAuthor(detection.manually_created ? "Argus Manual Detection" : "Argus AI Detection");
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
        if (!drzConfigured || !payload.coordinate) return
        // DRZ validates both against its enums; empty strings are rejected with a 422.
        if (!payload.subtype || !payload.detail) return
        if (isSendingDrz || drzSent) return

        setDrzError(null)
        const geometry: Geometry = {
            type: "Point",
            coordinates: [payload.coordinate.gps.lon, payload.coordinate.gps.lat],
        }
        const properties: Properties = {
            type: payload.detail,
            subtype: payload.subtype,
            // DRZ provenance enum: 0 AUTO, 1 MANUELL, 2 VERIFIED
            // (see api/app/services/drz_backend_sharing.py).
            detection: detection.manually_verified ? 2 : detection.manually_created ? 1 : 0,
            danger_level: dangerLevel === "true",
            name: payload.name,
            description: payload.description,
            datetime: payload.timestamp,
        }

        try {
            const resp = await sendToDrz({
                geometry,
                properties,
                detection_id: detection.id,
                attach_image: attachImage,
            })
            if (resp.error) {
                setDrzError({
                    message: resp.message || "Failed to send to DRZ.",
                    detail: resp.error,
                })
                return
            }
            if (resp.image_error) {
                // The POI is already created remotely and cannot be rolled back, so this is a
                // partial success: say so rather than inviting the operator to send it again.
                toast.warning("POI sent, but the image could not be attached", {
                    description: resp.image_error,
                })
            } else {
                toast.success(resp.message || "Detection sent to DRZ.")
            }
            // Show the confirmation on the button itself for a moment, then close.
            setDrzSent(true)
            window.setTimeout(handleClose, 700)
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
        setGroup("")
        setSubtype("")
        setDangerLevel("false")
        setAttachImage(false)
        setDrzError(null)
        setDrzSent(false)
        onClose()
    }

    // Dismiss a stale error whenever the user edits the form or switches send option.
    useEffect(() => {
        setDrzError(null)
    }, [name, description, author, detail, group, subtype, dangerLevel, attachImage, sendOption])

    const dateString = new Date(timestamp).toLocaleString()
    const activeGroup = DRZ_SUBTYPE_GROUPS.find((g) => g.key === group)
    const groupRules = drzGroupRules(group)
    // Read-only provenance, mirroring the DRZ detection enum sent at handleSend.
    const provenance = detection.manually_verified
        ? "Verified on site"
        : detection.manually_created
            ? "Added manually"
            : "Detected automatically"
    // DRZ requires both, and an empty string is what made "other" detections unsendable.
    const drzReady = Boolean(detection.coord && subtype && detail)

    return (
        <Dialog open={open} onOpenChange={(o) => { if (!o && !isSendingDrz && !drzSent) handleClose() }}>
            <DialogContent
                className="max-w-xl rounded-2xl p-6"
                onPointerDownOutside={(e) => { if (isSendingDrz || drzSent) e.preventDefault() }}
                onEscapeKeyDown={(e) => { if (isSendingDrz || drzSent) e.preventDefault() }}
            >
                <DialogHeader>
                    <DialogTitle>Share Object Detection</DialogTitle>
                </DialogHeader>

                {/* Without onSubmit the send button natively submits this form, which
                    navigates the page and aborts the in-flight request. */}
                <form className="space-y-4 mt-2" onSubmit={(e) => e.preventDefault()}>
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
                        <p>
                            <span className="font-semibold">Source:</span> {provenance}
                        </p>
                    </div>

                    {/* DRZ classification. One catalog (types/drz.ts) transcribed from the
                        partner OpenAPI spec, rather than a hardcoded block per Argus class —
                        which is what left "other" with no subtype to send at all. */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Category</Label>
                            <Select
                                value={group}
                                onValueChange={(g) => {
                                    setGroup(g)
                                    setSubtype("")
                                    // Keep the affiliation coherent with the new category —
                                    // it is often hidden, so it cannot be corrected by hand.
                                    setDetail(drzGroupRules(g).defaultMainType)
                                }}
                            >
                                <SelectTrigger><SelectValue placeholder="Select a category" /></SelectTrigger>
                                <SelectContent>
                                    {DRZ_SUBTYPE_GROUPS.map((g) => (
                                        <SelectItem key={g.key} value={g.key}>{g.label}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label>Subtype</Label>
                            <Select value={subtype} onValueChange={setSubtype} disabled={!activeGroup}>
                                <SelectTrigger>
                                    <SelectValue placeholder={activeGroup ? "Select a subtype" : "Pick a category first"} />
                                </SelectTrigger>
                                <SelectContent>
                                    {activeGroup?.options.map((o) => (
                                        <SelectItem key={o} value={o}>{o}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    {/* Affiliation is meaningless for a fire (it names an organisation, and a
                        fire belongs to none); hazard level is meaningless for a person, vehicle
                        or animal. Hidden fields keep their value and are still sent — DRZ
                        requires both. The rule follows the chosen category, not the Argus class,
                        so it stays right after a re-categorisation. */}
                    {(!groupRules.hideMainType || !groupRules.hideDangerLevel) && (
                        <div className="grid grid-cols-2 gap-4">
                        {!groupRules.hideMainType && (
                            <div className="space-y-2">
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Label className="cursor-help underline decoration-dotted underline-offset-4">
                                            Organizational affiliation
                                        </Label>
                                    </TooltipTrigger>
                                    <TooltipContent className="max-w-xs">
                                        <p>
                                            The organisation the object originates from — not what the object
                                            is. &ldquo;Fire brigade&rdquo; means the fire service, not a fire;
                                            an actual fire is filed under &ldquo;Action&rdquo; so the partner
                                            software draws the right icon.
                                        </p>
                                    </TooltipContent>
                                </Tooltip>
                                <Select value={detail} onValueChange={setDetail}>
                                    <SelectTrigger><SelectValue placeholder="Select an affiliation" /></SelectTrigger>
                                    <SelectContent>
                                        {DRZ_MAIN_TYPES.map(([v, l]) => (
                                            <SelectItem key={v} value={v}>{l}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}
                        {!groupRules.hideDangerLevel && (
                            <div className="space-y-2">
                                <Label>Hazard level</Label>
                                <Select value={dangerLevel} onValueChange={setDangerLevel}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        {DRZ_DANGER_LEVELS.map(([v, l]) => (
                                            <SelectItem key={v} value={v}>{l}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}
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

                    <div className="flex items-start space-x-2">
                        <Checkbox
                            id="attach-image"
                            checked={attachImage}
                            onCheckedChange={(c) => setAttachImage(!!c)}
                            className="mt-0.5"
                        />
                        <div className="space-y-0.5">
                            <Label htmlFor="attach-image">Attach the source image</Label>
                            <p className="text-xs text-muted-foreground">
                                Uploads {detection.image?.filename ?? "the full frame"} to the DRZ photo
                                service and links it to this POI. Off by default — a drone frame is several MB.
                            </p>
                        </div>
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
                        <Button type="button" variant="outline" onClick={handleClose} disabled={isSendingDrz}>Cancel</Button>
                        <ComboButton
                            value={sendOption}
                            options={[
                                { key: "email", label: "Send via Email" },
                                { key: "gps", label: "Download GPS POI" },
                                ...(drzConfigured ? [{ key: "drz", label: drzSent ? "Sent" : "Send to DRZ System" }] : []),
                            ]}
                            onChange={(key) => setSendOption(key as typeof sendOption)}
                            onAction={handleSend}
                            disabled={isSendingDrz || drzSent || (sendOption === "drz" && !drzReady)}
                        >
                            {isSendingDrz && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
                            {drzSent && <Check className="ml-2 h-4 w-4" />}
                        </ComboButton>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}
