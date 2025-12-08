import { useState, useEffect, useMemo, use, useRef } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import {
    ScanEye,
    ScanSearch,
    Car,
    Flame,
    PersonStanding,
    Funnel,
    Info,
    Eye,
    EyeOff
} from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { Report } from '@/types/report';
import type { Detection } from '@/types/detection';
import { getDetectionColor } from '@/types/detection';
import { useQueryClient } from '@tanstack/react-query';
import {
    useStartDetection,
    useDetectionStatusPolling,
    useFetchNewDetections,
    useDetections,
    useUpdateDetection,
    useIsDetectionRunning,
} from "@/hooks/detectionHooks";
import type { Image } from '@/types';
import { set } from 'date-fns';

function countDetections(detections: Detection[] | undefined, thresholds: { [key: string]: number } = {}) {
    console.log("Counting detections with thresholds:", thresholds);
    let summary: { [key: string]: number } = {};
    if (!detections || detections.length === 0 || Object.keys(thresholds).length === 0) return summary;

    detections.forEach((detection) => {
        if (!summary[detection.class_name]) {
            summary[detection.class_name] = 0;
        }
        if (detection.score < (thresholds[detection.class_name])) {
            return; // Skip detections below threshold
        }
        summary[detection.class_name] += 1;
    });
    return summary;
}



function initiateThresholds(detections: Detection[] | undefined) {
    if (!detections) return {};
    let thresholds: { [key: string]: number } = {};

    detections.forEach((detection) => {
        if (!(detection.class_name in thresholds)) {
            thresholds[detection.class_name] = 0.2; // Default threshold
        }
    });
    return thresholds;
}

function initiateCategoryVisibility(detections: Detection[]) {
    let visibility: { [key: string]: boolean } = {};
    if (!detections) return visibility;
    detections.forEach((detection) => {
        if (!(detection.class_name in visibility)) {
            visibility[detection.class_name] = true; // Default to visible
        }
    });
    return visibility;
}

function updateThresholds(detections: Detection[] | undefined, currentThresholds: { [key: string]: number }) {
    console.log("Updating thresholds with current:", currentThresholds);
    if (!detections) return currentThresholds;
    let thresholds = { ...currentThresholds };

    detections.forEach((detection) => {
        if (!(detection.class_name in thresholds)) {
            thresholds[detection.class_name] = 0.2; // Default threshold
        }
    });
    console.log("Updated thresholds:", thresholds);
    return thresholds;
}

function updateCategoryVisibility(detections: Detection[] | undefined, currentVisibility: { [key: string]: boolean }) {
    if (!detections) return currentVisibility;
    let visibility = { ...currentVisibility };

    detections.forEach((detection) => {
        if (!(detection.class_name in visibility)) {
            visibility[detection.class_name] = true; // Default to visible
        }
    });
    return visibility;
}


interface Props {
    report_id: number;
    setThresholds: (thresholds: { [key: string]: number }) => void;
    thresholds: { [key: string]: number };
    setFilter: (filter: string[]) => void;
    filters: string[];
    visibleCategories: { [key: string]: boolean };
    setVisibleCategories: (visibility: { [key: string]: boolean }) => void;
}

export function DetectionCard({ report_id, setThresholds, thresholds, setFilter, filters, visibleCategories, setVisibleCategories }: Props) {
    const [pollingEnabled, setPollingEnabled] = useState(false);
    const isRunning = useIsDetectionRunning(report_id);
    const { data: detections, isLoading: isLoadingDetections, isError: isErrorDetections } = useDetections(report_id);
    const queryClient = useQueryClient();
    const detectionSummary = useMemo(() => { if (detections) return countDetections(detections, thresholds); }, [detections, thresholds]);
    var [hasDetections, setHasDetections] = useState(detections && detections.length > 0);
    const [detectionMode, setDetectionMode] = useState<"fast" | "medium" | "detailed" | "experimental" | undefined>(undefined);

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

    const startDetection = useStartDetection();
    const detectionStatus = useDetectionStatusPolling(report_id, pollingEnabled);
    const fetchNewDetections = useFetchNewDetections(report_id);
    const lastProgressRef = useRef(0);

    // const updateDetection = useUpdateDetection(report.report_id);

    useEffect(() => {
        if (!detectionStatus.data) return;

        const progress = detectionStatus.data.progress ?? 0;

        // If progress increased, request more detections
        if (progress > lastProgressRef.current) {
            fetchNewDetections.mutate();
        }
        lastProgressRef.current = progress;

        if (detectionStatus.data.status.toUpperCase() === "FINISHED" || detectionStatus.data.status.toUpperCase() === "ERROR") {
            setPollingEnabled(false);
            if (detectionStatus.data.status.toUpperCase() === "FINISHED") {
                // refresh detections by invalidating queries  ["report", report.report_id]
                queryClient.invalidateQueries({ queryKey: ["detections", report_id] });
                console.log("Detections should be updated");
            }
        }
    }, [detectionStatus.data]);


    const handleStart = () => {
        if (!detectionMode) return;

        startDetection.mutate(
            { reportId: report_id, processingMode: detectionMode },
            {
                onSuccess: () => {
                    queryClient.invalidateQueries({ queryKey: ["detections", report_id] });
                    setPollingEnabled(true);
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
            default:
                return "No information available for this mode.";
        }
    };


    return (
        <>
            <Card className="min-w-72 max-w-320 flex-2 relative overflow-hidden pb-3">
                <ScanEye className="absolute right-2 top-1 w-24 h-24 opacity-100 text-muted-foreground dark:text-white z-0 pointer-events-none" />

                {/* Gradient Overlay */}
                {/* <div className="absolute inset-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/60 to-white/0 dark:from-gray-900/100 dark:via-gray-900/70 dark:to-gray-900/0" /> */}
                <div className="absolute w-40 h-30 right-0 top-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/75 to-white/55 dark:from-gray-900/100 dark:via-gray-900/85 dark:to-gray-900/60" />

                <CardContent className="px-4 pt-1 flex flex-col items-start space-y-1 relative z-10">
                    {/* Title */}

                    <div className="flex justify-between items-start w-full">
                        <div className="text-xl font-bold leading-none">Object Detection</div>

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
                                                {count}
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
                                                        //setDetectionSummary(countDetections(report, newThresholds));
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
                                                    variant="outline"
                                                    size="icon"
                                                    className='p-0 m-0'
                                                    onClick={() => {
                                                        const thr = thresholds[key];
                                                        let newFilters = [];
                                                        if (!filters.includes(key)) {
                                                            newFilters.push(key);
                                                        }
                                                        setFilter(newFilters);
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
                                        value={detectionMode}
                                        onValueChange={(value) => setDetectionMode(value as "fast" | "medium" | "detailed" | "experimental" | undefined)}
                                    >
                                        <SelectTrigger className="w-[150px]"
                                            value={detectionMode}
                                        >
                                            <SelectValue placeholder="Analysis Mode" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="fast">Fast (Coarse)</SelectItem>
                                            <SelectItem value="medium">Medium (Refined)</SelectItem>
                                            <SelectItem value="detailed">Fine (Detailed)</SelectItem>
                                            <SelectItem value="experimental">Experimental (YOLOv11)</SelectItem>
                                            {/* Add more actions as needed */}
                                        </SelectContent>
                                    </Select>

                                    <Tooltip>
                                        <TooltipTrigger>

                                            <Button variant={`${detectionMode === undefined ? "outline" : "default"}`} size="sm" onClick={() => { handleStart() }} disabled={!pollingEnabled && (!detectionMode)}>
                                                Run Detection
                                            </Button>
                                        </TooltipTrigger>
                                        <TooltipContent>
                                            {detectionMode === undefined ? "Select analysis mode first" : "Start AI detection processing"}
                                        </TooltipContent>

                                    </Tooltip>
                                </div>
                                {detectionMode && (
                                    <div className="rounded-md border p-2 mt-2 text-sm border-gray-400 bg-gray-200 text-muted-foreground dark:bg-gray-800 dark:border-gray-700">
                                        <p className="m-0">
                                            <Info className="inline-block w-3 h-3 align-middle mr-1" />
                                            {infotextForMode(detectionMode)}
                                        </p>
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
