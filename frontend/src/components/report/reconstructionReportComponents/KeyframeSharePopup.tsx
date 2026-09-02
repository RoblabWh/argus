import { useEffect, useMemo, useState } from "react";
import { Download, Loader2, Send, Share2 } from "lucide-react";
import { toast } from "sonner";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { CoordinatePickerMap, type Coordinate } from "@/components/shared/CoordinatePickerMap";
import { getKeyframeDownloadUrl } from "@/api";
import { useSendKeyframeToDrz } from "@/hooks/useSendKeyframeToDrz";
import { useSettings } from "@/hooks/settingsHooks";
import type { Keyframe, KeyframeGeo } from "@/types/reconstruction";

interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    reportId: number;
    reportTitle?: string;
    index: number;
    keyframe: Keyframe | undefined;
    /** Coordinates already picked for this report, keyed by keyframe index. */
    keyframeGeo: Record<string, KeyframeGeo>;
}

/**
 * Download the current panorama, or send it to the DRZ/IAIS photo service.
 *
 * 360° reconstructions are built from SLAM poses in a local metric frame, so keyframes
 * carry no GPS at all — DRZ needs a coordinate, and the user supplies it on the map here.
 */
export function KeyframeSharePopup({
    open, onOpenChange, reportId, reportTitle, index, keyframe, keyframeGeo,
}: Props) {
    const { data: settings } = useSettings();
    const drzConfigured = Boolean(settings?.DRZ_BACKEND_URL);

    const stored = keyframeGeo?.[String(index)];
    const defaultName = `${reportTitle || `Report ${reportId}`} — Keyframe ${index + 1}`;

    const [activeTab, setActiveTab] = useState("download");
    const [coord, setCoord] = useState<Coordinate | null>(null);
    const [name, setName] = useState(defaultName);
    const [description, setDescription] = useState("");
    const [isDownloading, setIsDownloading] = useState(false);
    const [errorText, setErrorText] = useState("");

    const { mutateAsync: sendToDrz, isPending: isSending } = useSendKeyframeToDrz();
    const isBusy = isDownloading || isSending;

    // Fall back to another keyframe's position so the map opens near the flight
    const nearbyGeo = useMemo(() => {
        const entries = Object.values(keyframeGeo || {});
        return entries.length > 0 ? { lat: entries[0].lat, lon: entries[0].lon } : undefined;
    }, [keyframeGeo]);

    // Reset to this keyframe's stored state every time the dialog opens
    useEffect(() => {
        if (!open) return;
        setErrorText("");
        setCoord(stored ? { lat: stored.lat, lon: stored.lon } : null);
        setName(stored?.name || defaultName);
        setDescription(stored?.description || "");
        if (!drzConfigured) setActiveTab("download");
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, index]);

    const handleOpenChange = (next: boolean) => {
        if (!next && isBusy) return;
        onOpenChange(next);
    };

    const handleDownload = async () => {
        setIsDownloading(true);
        setErrorText("");
        try {
            const response = await fetch(getKeyframeDownloadUrl(reportId, index));
            if (!response.ok) throw new Error(`Download failed: ${response.status}`);

            const blob = await response.blob();
            const disposition = response.headers.get("content-disposition");
            const match = disposition?.match(/filename="?(.+?)"?$/);
            const downloadName = match?.[1] || `report${reportId}_keyframe${index + 1}.jpg`;

            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = downloadName;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);

            setIsDownloading(false);
            onOpenChange(false);
        } catch (err) {
            setErrorText(err instanceof Error ? err.message : "Download failed.");
            setIsDownloading(false);
        }
    };

    const handleSend = async () => {
        if (!coord || !name.trim()) return;
        setErrorText("");
        try {
            const resp = await sendToDrz({
                reportId,
                index,
                body: { lat: coord.lat, lon: coord.lon, name: name.trim(), description: description.trim() || null },
            });
            if (resp.success) {
                toast.success(stored?.iais_photo_id ? "Panorama updated in the DRZ system" : "Panorama sent to the DRZ system");
                onOpenChange(false);
            } else {
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
                onPointerDownOutside={(e) => { if (isBusy) e.preventDefault(); }}
                onEscapeKeyDown={(e) => { if (isBusy) e.preventDefault(); }}
            >
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Share2 className="size-4" />
                        Share Keyframe {index + 1}
                    </DialogTitle>
                </DialogHeader>

                <Tabs
                    value={activeTab}
                    onValueChange={(v) => { if (!isBusy) { setErrorText(""); setActiveTab(v); } }}
                    className="mt-2"
                >
                    <TabsList className="w-full">
                        <TabsTrigger value="download" disabled={isBusy && activeTab !== "download"}>
                            <Download className="size-3.5" />
                            Download
                        </TabsTrigger>
                        {drzConfigured && (
                            <TabsTrigger value="drz" disabled={isBusy && activeTab !== "drz"}>
                                <Send className="size-3.5" />
                                DRZ
                            </TabsTrigger>
                        )}
                    </TabsList>

                    {/* Download the panorama */}
                    <TabsContent value="download" className="space-y-4">
                        <p className="text-sm text-muted-foreground">
                            Downloads this keyframe as a full-resolution equirectangular panorama
                            {keyframe?.filename ? ` (${keyframe.filename})` : ""}.
                        </p>
                        {errorText && <p className="text-xs text-red-600">{errorText}</p>}
                        <Button onClick={handleDownload} disabled={isDownloading} className="w-full">
                            {isDownloading
                                ? <><Loader2 className="h-4 w-4 animate-spin" /> Preparing download…</>
                                : <><Download className="h-4 w-4" /> Download Panorama</>}
                        </Button>
                    </TabsContent>

                    {/* Send to the DRZ/IAIS photo service */}
                    {drzConfigured && (
                        <TabsContent value="drz" className="space-y-4">
                            <p className="text-sm text-muted-foreground">
                                360° reconstructions are not georeferenced, so pick where this panorama
                                was taken before sending it to the DRZ system.
                            </p>

                            <div className="space-y-2">
                                <Label>Name</Label>
                                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={defaultName} />
                            </div>

                            <div className="space-y-2">
                                <Label>Description <span className="text-muted-foreground">(optional)</span></Label>
                                <Textarea
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    placeholder="What can be seen here?"
                                    rows={2}
                                />
                            </div>

                            <div className="space-y-2">
                                <Label>Position</Label>
                                <CoordinatePickerMap
                                    value={coord}
                                    onChange={setCoord}
                                    defaultCenter={nearbyGeo}
                                    visible={open && activeTab === "drz"}
                                />
                            </div>

                            {stored?.iais_photo_id && (
                                <p className="text-xs text-muted-foreground">
                                    Already sent as photo <span className="font-mono">{stored.iais_photo_id}</span> — sending again updates it.
                                </p>
                            )}
                            {errorText && <p className="text-xs text-red-600 break-words">{errorText}</p>}

                            <Button
                                onClick={handleSend}
                                disabled={!coord || !name.trim() || isSending}
                                className="w-full"
                            >
                                {isSending
                                    ? <><Loader2 className="h-4 w-4 animate-spin" /> Sending…</>
                                    : <><Send className="h-4 w-4" /> Send to DRZ</>}
                            </Button>
                        </TabsContent>
                    )}
                </Tabs>
            </DialogContent>
        </Dialog>
    );
}
