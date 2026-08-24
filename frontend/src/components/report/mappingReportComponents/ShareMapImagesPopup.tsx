import { useState, useEffect } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import type { Map } from "@/types/map"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { useMaps } from "@/hooks/useMaps"
import { getExportReportUrl, getMapDownloadUrl, type MapDownloadFormat } from "@/api"
import { useSendMapToDrz } from "@/hooks/useSendMapToDRZ";
import { Loader2, Download, FolderArchive, Send } from "lucide-react"


interface ExportPopupProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    reportId: number
    drzBackendApi?: string | null
    isExporting: boolean
    onExportingChange: (exporting: boolean) => void
}

function MapSelector({ maps, selectedMapId, onSelect, isLoading, isError }: {
    maps: Map[] | undefined
    selectedMapId: number | null
    onSelect: (id: number) => void
    isLoading: boolean
    isError: boolean
}) {
    if (isLoading) return <div className="text-sm text-muted-foreground">Loading maps...</div>
    if (isError) return <div className="text-sm text-red-600">Error loading maps.</div>
    if (!maps || maps.length === 0) return <div className="text-sm text-muted-foreground">No orthophotos available for this report.</div>

    return (
        <div className="space-y-2">
            <Label>Map</Label>
            <Select
                value={selectedMapId ? selectedMapId.toString() : ""}
                onValueChange={(value) => onSelect(parseInt(value))}
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
    )
}

export function ExportPopup({
    open,
    onOpenChange,
    reportId,
    drzBackendApi,
    isExporting,
    onExportingChange,
}: ExportPopupProps) {
    const [activeTab, setActiveTab] = useState("export")
    const [selectedMapId, setSelectedMapId] = useState<number | null>(null)
    const [filename, setFilename] = useState<string>("")
    const [downloadFormat, setDownloadFormat] = useState<MapDownloadFormat>("png")
    const [isDownloading, setIsDownloading] = useState(false)
    const [layerName, setLayerName] = useState<string>(`argus_report${reportId}`)
    const [serverMessage, setServerMessage] = useState<string>("")
    const [exportError, setExportError] = useState<string>("")

    const { data: maps, isLoading: isLoadingMaps, isError: isErrorMaps } = useMaps(reportId)
    const { mutateAsync: sendToDrz, isPending: isSending } = useSendMapToDrz()

    const hasMaps = maps && maps.length > 0
    const isBusy = isExporting || isSending || isDownloading

    const selectedMap = maps?.find((m: Map) => m.id === selectedMapId)
    // Maps built before UTM bounds were stored can only be projected to WGS84
    const hasUtmBounds = Boolean(selectedMap?.bounds?.utm)

    // Select first map automatically
    useEffect(() => {
        if (maps && maps.length > 0 && !selectedMapId) {
            setSelectedMapId(maps[0].id)
        }
    }, [maps, selectedMapId])

    // Initialize filename when a map is selected
    useEffect(() => {
        if (selectedMap) {
            setFilename(selectedMap.name?.replace(/\.[^/.]+$/, "") || "orthophoto")
        }
    }, [selectedMap])

    // Fall back to PNG if the chosen format isn't available for this map
    useEffect(() => {
        if (downloadFormat === "geotiff_utm" && selectedMap && !hasUtmBounds) {
            setDownloadFormat("png")
        }
    }, [downloadFormat, selectedMap, hasUtmBounds])

    useEffect(() => {
        if (open) {
            setServerMessage("")
            setExportError("")
        }
    }, [open])

    // Lock to export tab while exporting
    useEffect(() => {
        if (isExporting) setActiveTab("export")
    }, [isExporting])

    const resetFields = () => {
        setSelectedMapId(null)
        setFilename("")
        setDownloadFormat("png")
        setLayerName(`argus_report${reportId}`)
        setServerMessage("")
        setExportError("")
    }

    const handleClose = () => {
        if (isBusy) return
        resetFields()
        onOpenChange(false)
    }

    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen && isBusy) return
        onOpenChange(nextOpen)
        if (!nextOpen) {
            resetFields()
        }
    }

    const handleExportProject = async () => {
        onExportingChange(true)
        setExportError("")
        try {
            const response = await fetch(getExportReportUrl(reportId))
            if (!response.ok) {
                throw new Error(`Export failed: ${response.status}`)
            }
            const blob = await response.blob()
            const disposition = response.headers.get("content-disposition")
            const filenameMatch = disposition?.match(/filename="?(.+?)"?$/)
            const downloadName = filenameMatch?.[1] || `report_${reportId}.zip`

            const url = URL.createObjectURL(blob)
            const link = document.createElement("a")
            link.href = url
            link.download = downloadName
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            URL.revokeObjectURL(url)

            onExportingChange(false)
            handleClose()
        } catch (err: any) {
            console.error("Export failed:", err)
            setExportError(err?.message || "Export failed.")
            onExportingChange(false)
        }
    }

    const handleDownload = async () => {
        if (!selectedMap) return

        setIsDownloading(true)
        setExportError("")
        try {
            const response = await fetch(getMapDownloadUrl(reportId, selectedMap.id, downloadFormat, filename))
            if (!response.ok) {
                const detail = await response.json().catch(() => null)
                throw new Error(detail?.detail || `Download failed: ${response.status}`)
            }
            const blob = await response.blob()
            const disposition = response.headers.get("content-disposition")
            const filenameMatch = disposition?.match(/filename="?(.+?)"?$/)
            const downloadName = filenameMatch?.[1]
                || `${filename || "orthophoto"}${downloadFormat === "png" ? ".png" : ".tif"}`

            const url = URL.createObjectURL(blob)
            const link = document.createElement("a")
            link.href = url
            link.download = downloadName
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            URL.revokeObjectURL(url)

            // close directly — handleClose would still see the stale isBusy
            setIsDownloading(false)
            resetFields()
            onOpenChange(false)
        } catch (err: any) {
            console.error("Download failed:", err)
            setExportError(err?.message || "Download failed.")
            setIsDownloading(false)
        }
    }

    const handleSendToDrz = async () => {
        if (!selectedMapId || !maps) return
        const selectedMap = maps.find((m: Map) => m.id === selectedMapId)
        if (!selectedMap) return

        setServerMessage("")
        try {
            const resp = await sendToDrz({
                reportId,
                mapId: selectedMap.id,
                layerName,
            })
            if (resp.success) {
                handleClose()
            } else {
                setServerMessage(resp.message || "Upload failed.")
            }
        } catch (err: any) {
            setServerMessage(err?.message || "Upload failed.")
        }
    }

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent
                className="max-w-xl rounded-2xl p-6"
                onPointerDownOutside={(e) => { if (isBusy) e.preventDefault() }}
                onEscapeKeyDown={(e) => { if (isBusy) e.preventDefault() }}
            >
                <DialogHeader>
                    <DialogTitle>Export Report</DialogTitle>
                </DialogHeader>

                <Tabs
                    value={activeTab}
                    onValueChange={(v) => {
                        if (isBusy) return
                        setExportError("")
                        setServerMessage("")
                        setActiveTab(v)
                    }}
                    className="mt-2"
                >
                    <TabsList className="w-full">
                        <TabsTrigger value="export" disabled={isBusy && activeTab !== "export"}>
                            <FolderArchive className="size-3.5" />
                            Project ZIP
                        </TabsTrigger>
                        <TabsTrigger value="download" disabled={isBusy && activeTab !== "download"}>
                            <Download className="size-3.5" />
                            Orthophoto
                        </TabsTrigger>
                        {drzBackendApi && (
                            <TabsTrigger value="drz" disabled={isBusy && activeTab !== "drz"}>
                                <Send className="size-3.5" />
                                DRZ
                            </TabsTrigger>
                        )}
                    </TabsList>

                    {/* Export Project ZIP */}
                    <TabsContent value="export" className="space-y-4">
                        <p className="text-sm text-muted-foreground">
                            Exports the complete report as a ZIP archive for backup or transfer. Packing the project may take up to a couple of minutes, depending on your report size. Once ready, the download will start automatically.
                        </p>
                        {exportError && (
                            <p className="text-xs text-red-600">{exportError}</p>
                        )}
                        <Button onClick={handleExportProject} disabled={isExporting} className="w-full">
                            {isExporting ? (
                                <><Loader2 className="h-4 w-4 animate-spin" /> Preparing download...</>
                            ) : (
                                <><FolderArchive className="h-4 w-4" /> Export Project</>
                            )}
                        </Button>
                    </TabsContent>

                    {/* Download Orthophoto */}
                    <TabsContent value="download" className="space-y-4">
                        <p className="text-sm text-muted-foreground">
                            Downloads the selected orthophoto to your device. GeoTIFF keeps the
                            georeferencing, so the map can be loaded into QGIS or ArcGIS.
                        </p>
                        <MapSelector
                            maps={maps}
                            selectedMapId={selectedMapId}
                            onSelect={setSelectedMapId}
                            isLoading={isLoadingMaps}
                            isError={isErrorMaps}
                        />
                        {selectedMap && (
                            <>
                                <div className="space-y-2">
                                    <Label>Format</Label>
                                    <Select
                                        value={downloadFormat}
                                        onValueChange={(value) => setDownloadFormat(value as MapDownloadFormat)}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="png">PNG (image only)</SelectItem>
                                            <SelectItem value="geotiff_wgs84">GeoTIFF (WGS84 / EPSG:4326)</SelectItem>
                                            <SelectItem value="geotiff_utm" disabled={!hasUtmBounds}>
                                                GeoTIFF (UTM){!hasUtmBounds && " — not available for this map"}
                                            </SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label>Filename</Label>
                                    <Input
                                        value={filename}
                                        onChange={(e) => setFilename(e.target.value)}
                                        placeholder="Enter filename"
                                    />
                                </div>
                            </>
                        )}
                        {exportError && (
                            <p className="text-xs text-red-600">{exportError}</p>
                        )}
                        <Button onClick={handleDownload} disabled={!hasMaps || isDownloading} className="w-full">
                            {isDownloading ? (
                                <><Loader2 className="h-4 w-4 animate-spin" /> Preparing download...</>
                            ) : (
                                <><Download className="h-4 w-4" /> Download Orthophoto</>
                            )}
                        </Button>
                    </TabsContent>

                    {/* Send to DRZ */}
                    {drzBackendApi && (
                        <TabsContent value="drz" className="space-y-4">
                            <p className="text-sm text-muted-foreground">
                                Sends the selected orthophoto to the DRZ system.
                            </p>
                            <MapSelector
                                maps={maps}
                                selectedMapId={selectedMapId}
                                onSelect={setSelectedMapId}
                                isLoading={isLoadingMaps}
                                isError={isErrorMaps}
                            />
                            <div className="space-y-2">
                                <Label>Layer Name</Label>
                                <Input
                                    value={layerName}
                                    onChange={(e) => setLayerName(e.target.value)}
                                    placeholder={`argus_report${reportId}`}
                                />
                            </div>
                            {serverMessage && (
                                <p className="text-xs text-red-600">{serverMessage}</p>
                            )}
                            <Button onClick={handleSendToDrz} disabled={!hasMaps || isSending} className="w-full">
                                {isSending ? (
                                    <><Loader2 className="h-4 w-4 animate-spin" /> Sending...</>
                                ) : (
                                    <><Send className="h-4 w-4" /> Send to DRZ</>
                                )}
                            </Button>
                        </TabsContent>
                    )}
                </Tabs>
            </DialogContent>
        </Dialog>
    )
}
