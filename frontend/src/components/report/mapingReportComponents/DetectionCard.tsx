import { useState } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal, ScanEye, ScanSearch, Car, Flame, PersonStanding, Funnel, Info } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { Report } from '@/types/report';
import { EditReportPopup } from "../EditReportPopup";

interface Props {
    report: Report;

}

function countDetections(report: Report, thresholds: { [key: string]: number } = {}) {
    let images = report.mapping_report?.images || [];
    let summary: { [key: string]: number } = {};
    if (images.length === 0 || Object.keys(thresholds).length === 0) return summary;

    images.forEach((image) => {
        image.detections.forEach((detection) => {
            if (!summary[detection.class_name]) {
                summary[detection.class_name] = 0;
            }
            if (detection.score < (thresholds[detection.class_name])) {
                return; // Skip detections below threshold
            }
            summary[detection.class_name] += 1;
        });
    });
    return summary;
}

function initiateThresholds(report: Report) {
    let images = report.mapping_report?.images || [];
    let thresholds: { [key: string]: number } = {};

    images.forEach((image) => {
        image.detections.forEach((detection) => {
            if (!(detection.class_name in thresholds)) {
                thresholds[detection.class_name] = 0.4; // Default threshold
            }
        });
    });
    return thresholds;
}



export function DetectionCard({ report }: Props) {
    const isProcessing = report.status === 'processing' || report.status === 'preprocessing';
    const [editPopupOpen, setEditPopupOpen] = useState(false);
    const [thresholds, setThresholds] = useState<{ [key: string]: number }>({ ...initiateThresholds(report) });
    const [detectionSummary, setDetectionSummary] = useState<{ [key: string]: number }>({ ...countDetections(report, thresholds) });
    const [detectionMode, setDetectionMode] = useState<"fast" | "medium" | "detailed" | undefined>(undefined);
    const hasDetections = Object.keys(detectionSummary).length > 0;
    const onEditDetailsClick = () => {
        setEditPopupOpen(true);
    };

    const selectObjectIcon = (objectType: string) => {
        switch (objectType) {
            case 'vehicle':
                return <Car className="w-4 h-4 mr-2" />;
            case 'fire':
                return <Flame className="w-4 h-4 mr-2" />;
            case 'human':
                return <PersonStanding className="w-4 h-4 mr-2" />;
            default:
                return <ScanSearch className="w-4 h-4 mr-2" />;
        }
    };

    const infotextForMode = (mode: string) => {
        switch (mode) {
            case 'fast':
                return "Fast mode scans the whole image quickly. Small details may be missed.";
            case 'medium':
                return "Medium mode splits the image into 4 parts for better detection. Slower than fast, but more accurate.";
            case 'detailed':
                return "Detailed mode processes images at full resolution for maximum detail. Much slower, best for high-altitude or fine-detail.";
            default:
                return "";
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
                    {hasDetections ?(
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
                                    {Object.entries(detectionSummary).map(([key, count]) => (
                                        <TableRow key={key} className="cursor-pointer hover:bg-muted transition-colors p-1">
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
                                                    value={thresholds[key] || 0.4}
                                                    onChange={(e) => {
                                                        const newThresholds = { ...thresholds, [key]: parseFloat(e.target.value) };
                                                        setThresholds(newThresholds);
                                                        setDetectionSummary(countDetections(report, newThresholds));
                                                    }}
                                                    className="w-full m-0 "
                                                />
                                            </TableCell>
                                            <TableCell className="w-0 py-1">
                                                <Button
                                                    variant="outline"
                                                    size="icon"
                                                    className='p-0 m-0'
                                                    onClick={() => {
                                                        console.log(`Filter by ${key} clicked`);
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
                    ):
                        <div className="text-muted-foreground mt-2 text-xs">
                            {isProcessing ? (
                                <span>Detection will be available after processing completes.</span>
                            ) : (
                                <span>No detections found. Run AI Detection below.</span>
                            )}
                        </div>
                    }


                    {/* Bottom section */}
                    <div className="w-full mt-4">
                        {isProcessing ? (
                            <div className="w-full">

                                {report.progress !== undefined && (
                                    <>
                                        <Progress value={report.progress} />
                                        <p className="text-sm text-muted-foreground mt-1">
                                            {report.status} — {Math.round(report.progress)}%
                                        </p>
                                    </>
                                )}
                            </div>
                        ) : (
                            <div className="w-full flex flex-col">

                                <div className="w-full flex flex-row justify-between items-center">

                                    <Select
                                        value={detectionMode}
                                        onValueChange={(value) => setDetectionMode(value as "fast" | "medium" | "detailed")}
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
                                            {/* Add more actions as needed */}
                                        </SelectContent>
                                    </Select>


                                    <Button variant="outline" size="sm" onClick={onEditDetailsClick}>
                                        Run Detection
                                    </Button>
                                </div>
                                {detectionMode && (
                                    <div className="rounded-md border p-2 mt-2 text-sm border-gray-400 bg-gray-200 text-muted-foreground">
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
            <EditReportPopup
                open={editPopupOpen}
                onOpenChange={setEditPopupOpen}
                reportId={report.report_id}
                initialTitle={report.title}
                initialDescription={report.description}
            />
        </>
    );

}
