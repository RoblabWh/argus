import { useState, useEffect } from "react"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogClose } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { ComboButton } from "@/components/ComboButton"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { Map } from "@/types/map"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { useMaps } from "@/hooks/useMaps"
import { getApiUrl } from "@/api"
import { useSendMapToDrz } from "@/hooks/useSendMapToDRZ";
import { Loader2 } from "lucide-react"


interface ShareMapImagesPopupProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    reportId: number
    drzBackendApi?: string | null
}

export function ShareMapImagesPopup({
    open,
    onOpenChange,
    reportId,
    drzBackendApi,
}: ShareMapImagesPopupProps) {
    const [sendOption, setSendOption] = useState<"email" | "drz" | "download">("download")
    const [selectedMapId, setSelectedMapId] = useState<number | null>(null)
    const [filename, setFilename] = useState<string>("")
    const [layerName, setLayerName] = useState<string>(`argus_report${reportId}`)
    const [serverMessage, setServerMessage] = useState<string>("");

    const { data: maps, isLoading: isLoadingMaps, isError: isErrorMaps } = useMaps(reportId)
    const apiUrl = getApiUrl()
    const { mutateAsync: sendToDrz, isPending: isSending } = useSendMapToDrz();


    // Select first map automatically
    useEffect(() => {
        if (maps && maps.length > 0 && !selectedMapId) {
            setSelectedMapId(maps[0].id)
        }
    }, [maps, selectedMapId])

    // Initialize filename when a map is selected
    useEffect(() => {
        if (selectedMapId && maps) {
            const selected = maps.find((m: Map) => m.id === selectedMapId)
            if (selected) {
                const baseName = selected.name?.replace(/\.[^/.]+$/, "") || "orthophoto"
                setFilename(baseName)
            }
        }
    }, [selectedMapId, maps])

    useEffect(() => {
        setServerMessage("");
    }, [sendOption, selectedMapId, layerName]);

    const handleSend = async () => {
        if (!selectedMapId || !maps) return

        const selectedMap = maps.find((m: Map) => m.id === selectedMapId)
        if (!selectedMap) return

        const payload = {
            id: selectedMap.id,
            filename: filename,
            reportId: reportId,
            layername: layerName,
        }

        switch (sendOption) {
            case "drz":
                console.log("Send to DRZ System", payload)
                try {
                    const resp = await sendToDrz({
                        reportId,
                        mapId: selectedMap.id,
                        layerName,
                    });
                    const ok = resp.success
                    console.log(resp)
                    if (ok) {
                        handleClose();
                    } else {
                        setServerMessage(resp.message || "Upload failed.");
                    }
                } catch (err: any) {
                    setServerMessage(err?.message || "Upload failed.");
                }

                break

            case "download":
                try {
                    console.log("Downloading orthophoto:", payload)
                    const url = (`${apiUrl}/${selectedMap.url}`)
                    const link = document.createElement("a");
                    link.href = url;
                    link.target = "_blank";
                    link.download = ""; // Let browser infer filename from response headers
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                } catch (err) {
                    console.error("Failed to download map:", err)
                }
                handleClose()
                break
        }

    }

    const handleClose = () => {
        setSelectedMapId(null)
        setFilename("")
        setLayerName(`argus_report${reportId}`)
        setServerMessage("");
        onOpenChange(false)
    }

    useEffect(() =>{
        if(open){
            setServerMessage("");
        }
    },[open])

    // Info message depending on state
    const infoText = (() => {
        if (isLoadingMaps) return "Loading available maps..."
        if (isErrorMaps) return "Could not load maps."
        if (!maps || maps.length === 0) return "No orthophotos available for this report."
        if (sendOption === "download") return "Downloads the selected orthophoto to your device."
        if (sendOption === "drz") return "Sends the selected orthophoto to the DRZ system."
        return ""
    })()

    const hasMaps = maps && maps.length > 0

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-xl rounded-2xl p-6">
                <DialogHeader>
                    <DialogTitle>Share Orthophoto</DialogTitle>
                </DialogHeader>

                <form className="space-y-4 mt-2" onSubmit={(e) => e.preventDefault()}>
                    {isLoadingMaps ? (
                        <div>Loading maps...</div>
                    ) : isErrorMaps ? (
                        <div>Error loading maps.</div>
                    ) : (
                        <>
                            {/* Map Selection */}
                            {(maps && maps.length > 0) && (
                                <div className="space-y-2">
                                    <Label>Map</Label>
                                    <Select
                                        value={selectedMapId ? selectedMapId.toString() : ""}
                                        onValueChange={(value) => setSelectedMapId(parseInt(value))}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Select a map" />
                                        </SelectTrigger>
                                        <SelectContent>

                                            {maps.map((map: Map) => (
                                                <SelectItem key={map.id} value={map.id.toString()}>
                                                    {map.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}

                            {/* Filename Input */}
                            {selectedMapId && (
                                <div className="space-y-2">
                                    <Label>Filename</Label>
                                    <Input
                                        value={filename}
                                        onChange={(e) => setFilename(e.target.value)}
                                        placeholder="Enter filename"
                                        required
                                    />
                                </div>
                            )}

                            {/* Conditional Layer Name for DRZ */}
                            {sendOption === "drz" && (
                                <div className="space-y-2">
                                    <Label>Layer Name</Label>
                                    <Input
                                        value={layerName}
                                        onChange={(e) => setLayerName(e.target.value)}
                                        placeholder={`argus_report${reportId}`}
                                    />
                                </div>
                            )}
                        </>
                    )}

                    {/* Info Text */}
                    {/* Info Text + Server Message */}
                    <div className="space-y-1">
                        <p className="text-xs text-muted-foreground italic">{infoText}</p>
                        {serverMessage && (
                            <p className="text-xs text-red-600">{serverMessage}</p>
                        )}
                    </div>

                    <DialogFooter className="pt-4 flex justify-between">
                        <DialogClose asChild>
                            <Button variant="outline" >
                                Cancel
                            </Button>
                        </DialogClose>
                        <ComboButton
                            value={sendOption}
                            options={[
                                { key: "download", label: "Download Orthophoto" },
                                ...(drzBackendApi ? [{ key: "drz", label: "Send to DRZ System" }] : []),
                            ]}
                            onChange={(key) => setSendOption(key as typeof sendOption)}
                            onAction={handleSend}
                            disabled={!hasMaps || isSending}
                        >
                            {isSending && (
                                <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                            )}
                        </ComboButton>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}
