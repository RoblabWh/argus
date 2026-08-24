import { useState, useEffect, useMemo, useRef } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
    ScanEye,
    ScanSearch,
    Car,
    Flame,
    PersonStanding,
    Funnel,
    Info,
    Eye,
    EyeOff,
    Scissors,
    Boxes,
    Layers,
    Group,
    X
} from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { Detection, DetectionDisplayMode } from '@/types/detection';
import { getDetectionColor } from '@/types/detection';
import { useDetectionColorsVersion } from '@/hooks/useDetectionColors';
import { useQueryClient } from '@tanstack/react-query';
import {
    useStartDetection,
    useDetectionStatusPolling,
    useFetchNewDetections,
    useDetections,
    useIsDetectionRunning,
} from "@/hooks/detectionHooks";
import {
    countDetections,
    countReduced,
    reduceDetections,
    initiateThresholds,
    initiateCategoryVisibility,
    updateThresholds,
    updateCategoryVisibility,
} from "@/utils/detectionUtils";
import { useMaps } from "@/hooks/useMaps";
import { useImages } from "@/hooks/imageHooks";
import { useSseActive, useSseWake } from "@/hooks/useReportEvents";


interface Props {
    report_id: number;
    setThresholds: (thresholds: { [key: string]: number }) => void;
    thresholds: { [key: string]: number };
    setFilter: (filter: string[]) => void;
    filters: string[];
    visibleCategories: { [key: string]: boolean };
    setVisibleCategories: (visibility: { [key: string]: boolean }) => void;
    detectionMode: DetectionDisplayMode;
    setDetectionMode: (v: DetectionDisplayMode) => void;
}

export function DetectionCard({ report_id, setThresholds, thresholds, setFilter, filters, visibleCategories, setVisibleCategories, detectionMode, setDetectionMode }: Props) {
    // Re-render when the configured detection colors change (getDetectionColor
    // reads a module-level store, not props).
    useDetectionColorsVersion();
    const [pollingEnabled, setPollingEnabled] = useState(false);
    const isRunning = useIsDetectionRunning(report_id);
    const { data: detections, isLoading: isLoadingDetections, isError: isErrorDetections } = useDetections(report_id);
    const { data: maps } = useMaps(report_id);
    const { data: images } = useImages(report_id);
    const hasVoronoi = useMemo(() =>
        maps?.some(m => m.map_elements?.some(el => el.voronoi_gps?.length)) ?? false
    , [maps]);
    const hasUniqueIds = useMemo(() =>
        detections?.some(d => d.unique_object_id != null) ?? false
    , [detections]);
    const queryClient = useQueryClient();
    // In "reduced" mode the count mirrors the map: distinct objects + Voronoi-clipped leftovers.
    // In "all" mode every detection above threshold is counted individually.
    const reducedSummary = useMemo(() => {
        if (!detections) return undefined;
        const summary = countReduced(reduceDetections(detections, images, maps, thresholds, "reduced"));
        // Seed every class with 0 so its row still renders even when fully reduced away.
        for (const det of detections) {
            if (!(det.class_name in summary)) summary[det.class_name] = 0;
        }
        return summary;
    }, [detections, images, maps, thresholds]);
    const allSummary = useMemo(
        () => (detections ? countDetections(detections, thresholds) : undefined),
        [detections, thresholds]
    );
    // The table shows the count for the active mode; the count-cell tooltip shows the other mode's.
    const detectionSummary = detectionMode === "reduced" ? reducedSummary : allSummary;
    const alternateSummary = detectionMode === "reduced" ? allSummary : reducedSummary;
    var [hasDetections, setHasDetections] = useState(detections && detections.length > 0);
    const [analysisMode, setAnalysisMode] = useState<"fast" | "medium" | "detailed" | "experimental" | "fire" | undefined>(undefined);
    // Which mode's info text the user dismissed — switching modes shows the box again.
    const [dismissedInfoMode, setDismissedInfoMode] = useState<string | undefined>(undefined);

    useEffect(() => {
        if (detections) {
            setHasDetections(detections.length > 0);
            if (Object.keys(thresholds).length == 0) {
                setThresholds(initiateThresholds(detections));
                setVisibleCategories(initiateCategoryVisibility(detections));
            }
            else {
                setThresholds(updateThresholds(detections, thresholds));
                setVisibleCategories(updateCategoryVisibility(detections, visibleCategories));
            }
        }
    }, [detections]);

    // enable polling automatically if backend says process is running
    useEffect(() => {
        if (isRunning.data) {
            setPollingEnabled(true);
        }
    }, [isRunning.data]);

    const sseActive = useSseActive();
    const wakeSse = useSseWake();
    const startDetection = useStartDetection();
    const detectionStatus = useDetectionStatusPolling(report_id, pollingEnabled, sseActive);
    const fetchNewDetections = useFetchNewDetections(report_id);
    const lastProgressRef = useRef(0);

    useEffect(() => {
        if (!detectionStatus.data) return;

        const progress = detectionStatus.data.progress ?? 0;
        const status = detectionStatus.data.status.toUpperCase();
        const terminal = status === "FINISHED" || status === "ERROR" || status === "FAILED";

        // While running, pull newly-produced detections incrementally. Crucially, do NOT do
        // this on the terminal tick: the incremental merge snapshots the stale cache (no
        // unique_object_ids) and would clobber the authoritative refetch below — leaving the
        // re-id grouping invisible until a manual reload.
        if (!terminal && progress > lastProgressRef.current) {
            fetchNewDetections.mutate();
        }
        lastProgressRef.current = progress;

        if (terminal) {
            setPollingEnabled(false);
            if (status === "FINISHED") {
                // Authoritative full refetch — picks up re-id unique_object_ids (YOLO) or just
                // the final detections (old pipeline, no re-id). A second bounded refetch ~1.5s
                // later defeats the narrow race where a prior in-flight incremental merge
                // resolves after this invalidate.
                queryClient.invalidateQueries({ queryKey: ["detections", report_id] });
                const t = setTimeout(() => {
                    queryClient.invalidateQueries({ queryKey: ["detections", report_id] });
                }, 1500);
                return () => clearTimeout(t);
            }
        }
    }, [detectionStatus.data]);


    const handleStart = () => {
        if (!analysisMode) return;

        startDetection.mutate(
            { reportId: report_id, processingMode: analysisMode },
            {
                onSuccess: () => {
                    queryClient.invalidateQueries({ queryKey: ["detections", report_id] });
                    setPollingEnabled(true);
                    wakeSse(); // the stream is released while a report is idle
                },
            }
        );
    };


    const selectObjectIcon = (objectType: string) => {
        const color = getDetectionColor(objectType);

        var icon;

        switch (objectType) {
            case 'vehicle':
                icon = <Car className="w-4 h-4" color={"black"} />;
                break;
            case 'fire':
                icon = <Flame className="w-4 h-4" color={"black"} />;
                break;
            case 'human':
                icon = <PersonStanding className="w-4 h-4" color={"black"} />;
                break;
            default:
                icon = <ScanSearch className="w-4 h-4" color={"black"} />;
                break;
        }

        return (
            <div
                className={`w-6 h-6 flex items-center justify-center rounded-sm bg-[var(--tag-color)]  mr-1`}
                style={{ '--tag-color': color }}
            >
                {icon}
            </div>
        );
    };

    const infotextForMode = (mode: string) => {
        switch (mode) {
            case 'fast':
                return "Fast mode scans the whole image quickly. Small details may be missed.";
            case 'medium':
                return "Medium mode splits the image into 4 parts for better detection. Slower than fast, but more accurate.";
            case 'detailed':
                return "Detailed mode processes images at full resolution for maximum detail. Much slower, best for high-altitude or fine-detail.";
            case 'experimental':
                return "Experimental mode uses the latest YOLOv11 model. May not be integrated fully and could produce unexpected results.";
            case 'fire':
                return "Fire detection runs a dedicated fire model and only replaces previous fire results — object detections are kept. Fire shows up as a confidence overlay on the map.";
            default:
                return "No information available for this mode.";
        }
    };


    return (
        <>
            <Card className="min-w-72 max-w-320 flex-2 relative overflow-hidden pb-3">
                <ScanEye className="absolute right-2 top-1 w-24 h-24 opacity-100 text-muted-foreground dark:text-white z-0 pointer-events-none" />

                {/* Gradient Overlay */}
                <div className="absolute w-40 h-30 right-0 top-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/75 to-white/55 dark:from-gray-900/100 dark:via-gray-900/85 dark:to-gray-900/60" />

                <CardContent className="px-4 pt-1 flex flex-col items-start space-y-1 relative z-10">
                    {/* Title */}

                    <div className="flex justify-between items-center w-full">
                        <div className="text-xl font-bold leading-none">Object Detection</div>
                        {hasDetections && (hasUniqueIds || hasVoronoi) && (
                            <Tabs
                                value={detectionMode}
                                onValueChange={(v) => setDetectionMode(v as DetectionDisplayMode)}
                            >
                                <TabsList className="h-8">
                                    <TabsTrigger value="all" className="gap-1 px-2 py-1 text-xs">
                                        <Layers className="h-3.5 w-3.5" /> All
                                    </TabsTrigger>
                                    <TabsTrigger value="reduced" className="gap-1 px-2 py-1 text-xs">
                                        {hasUniqueIds ? <Group className="h-3.5 w-3.5" /> : <Scissors className="h-3.5 w-3.5" />}
                                        {hasUniqueIds ? "Grouped" : "Clipped"}
                                    </TabsTrigger>
                                </TabsList>
                            </Tabs>
                        )}
                    </div>

                    {/* Description */}
                    {hasDetections ? (
                        <div className="flex items-center justify-start w-full gap-1 mt-0">
                            <Table className="w-full ">
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-0">Type</TableHead>
                                        <TableHead className="w-0">Count</TableHead>
                                        <TableHead className="w-0">Threshold</TableHead>
                                        <TableHead className="w-0"></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {detectionSummary && Object.entries(detectionSummary).map(([key, count]) => (
                                        <TableRow key={key} className="hover:bg-muted transition-colors p-1">
                                            <TableCell className="w-0 py-1">
                                                <div className="flex items-center justify-center">
                                                    {selectObjectIcon(key)} {key}
                                                </div>
                                            </TableCell>
                                            <TableCell className="w-0 py-1">
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <span className="cursor-help">{count}</span>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        {detectionMode === "reduced"
                                                            ? `Ungrouped total: ${alternateSummary?.[key] ?? 0}`
                                                            : `Grouped: ${alternateSummary?.[key] ?? 0}`}
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TableCell>
                                            <TableCell className="w-0 p-auto py-1 ">
                                                <Input
                                                    type="number"
                                                    min="0"
                                                    max="1"
                                                    step="0.01"
                                                    value={thresholds[key]}
                                                    onChange={(e) => {
                                                        const newThresholds = { ...thresholds, [key]: parseFloat(e.target.value) };
                                                        setThresholds(newThresholds);
                                                    }}
                                                    className="w-full m-0 "
                                                />
                                            </TableCell>
                                            <TableCell className="w-0 py-1">
                                                <Button
                                                    variant={visibleCategories[key] ? "ghost" : "outline"}
                                                    size="icon"
                                                    className={`p-0 m-0 ml-1 ${visibleCategories[key] ? "outline-white" : ""}`}
                                                    onClick={() => {
                                                        const newVisibility = { ...visibleCategories, [key]: !visibleCategories[key] };
                                                        setVisibleCategories(newVisibility);
                                                    }}
                                                >
                                                    {visibleCategories[key] ? <Eye className="w-4 h-4 p-0 m-0" /> :
                                                        <EyeOff className="w-4 h-4 p-0 m-0" />
                                                    }
                                                </Button>

                                                <Button
                                                    variant={filters.includes(key) ? "default" : "outline"}
                                                    size="icon"
                                                    className='p-0 m-0'
                                                    onClick={() => {
                                                        const isCurrentlyFiltered = filters.includes(key);

                                                        if (isCurrentlyFiltered) {
                                                            // Clear filter and restore all categories to visible
                                                            setFilter([]);
                                                            const newVisibility: { [k: string]: boolean } = {};
                                                            Object.keys(visibleCategories).forEach(cat => {
                                                                newVisibility[cat] = true;
                                                            });
                                                            setVisibleCategories(newVisibility);
                                                        } else {
                                                            // Set filter to this category and hide all others
                                                            setFilter([key]);
                                                            const newVisibility: { [k: string]: boolean } = {};
                                                            Object.keys(visibleCategories).forEach(cat => {
                                                                newVisibility[cat] = cat === key;
                                                            });
                                                            setVisibleCategories(newVisibility);
                                                        }
                                                    }}
                                                >
                                                    <Funnel className="w-4 h-4 p-0 m-0" />
                                                </Button>

                                            </TableCell>

                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    ) :
                        <div className="text-muted-foreground mt-2 text-xs">
                            {pollingEnabled ? (
                                <span>Detection will be available after processing completes.</span>
                            ) : (
                                <span>No detections found. Run AI Detection below.</span>
                            )}
                        </div>
                    }


                    {/* Bottom section */}
                    <div className="w-full mt-2">
                        {pollingEnabled ? (
                            <div className="w-full">

                                {detectionStatus.data !== undefined && (
                                    <>
                                        <Progress value={detectionStatus.data.progress} />
                                        <p className="text-sm text-muted-foreground mt-1">
                                            {detectionStatus.data.message ? <>{detectionStatus.data.message}</> : <>{detectionStatus.data.status}</>} — {Math.round(detectionStatus.data.progress)}%
                                        </p>
                                    </>
                                )}
                            </div>
                        ) : (
                            <div className="w-full flex flex-col">

                                <div className="w-full flex flex-row justify-between items-center">

                                    <Select
                                        value={analysisMode}
                                        onValueChange={(value) => setAnalysisMode(value as "fast" | "medium" | "detailed" | "experimental" | "fire" | undefined)}
                                    >
                                        <SelectTrigger className="w-[150px]"
                                            value={analysisMode}
                                        >
                                            <SelectValue placeholder="Analysis Mode" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="fast">Fast (Coarse)</SelectItem>
                                            <SelectItem value="medium">Medium (Refined)</SelectItem>
                                            <SelectItem value="detailed">Fine (Detailed)</SelectItem>
                                            <SelectItem value="experimental">Experimental (YOLOv11)</SelectItem>
                                            <SelectItem value="fire">Fire (Experimental)</SelectItem>
                                        </SelectContent>
                                    </Select>

                                    <div className="flex items-center gap-2">
                                        <Tooltip>
                                            <TooltipTrigger>
                                                <Button variant={`${analysisMode === undefined ? "outline" : "default"}`} size="sm" onClick={() => { handleStart() }} disabled={!pollingEnabled && (!analysisMode)}>
                                                    Run Detection
                                                </Button>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                {analysisMode === undefined ? "Select analysis mode first" : "Start AI detection processing"}
                                            </TooltipContent>
                                        </Tooltip>
                                    </div>
                                </div>
                                {analysisMode && analysisMode !== dismissedInfoMode && (
                                    <div className="rounded-md border p-2 mt-2 text-sm border-gray-400 bg-gray-200 text-muted-foreground dark:bg-gray-800 dark:border-gray-700 flex items-start gap-2">
                                        <p className="m-0 flex-1">
                                            <Info className="inline-block w-3 h-3 align-middle mr-1" />
                                            {infotextForMode(analysisMode)}
                                        </p>
                                        <button
                                            type="button"
                                            aria-label="Dismiss info"
                                            onClick={() => setDismissedInfoMode(analysisMode)}
                                            className="shrink-0 rounded p-0.5 hover:bg-gray-300 dark:hover:bg-gray-700 hover:text-foreground transition-colors"
                                        >
                                            <X className="w-3.5 h-3.5" />
                                        </button>
                                    </div>

                                )}
                            </div>
                        )}

                    </div>
                </CardContent>
            </Card>
        </>
    );

}
