import { useState } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal, Square } from "lucide-react";
import type { Report } from '@/types/report';
import { EditReportPopup } from "../EditReportPopup";
import { ExportPopup } from './ShareMapImagesPopup';

interface Props {
    report: Report;
    onReprocessClicked: () => void;
    onStopProcessing?: () => void;
}

const statusColorMap: Record<string, string> = {
    queued: "text-gray-500",
    preprocessing: "text-yellow-600 dark:text-yellow-400",
    processing: "text-yellow-600 dark:text-yellow-400",
    completed: "text-green-600 dark:text-green-400",
    cancelled: "text-orange-600 dark:text-orange-400",
    failed: "text-red-600 dark:text-red-400",
    error: "text-red-600 dark:text-red-400",
};

export function GeneralDataCard({ report, onReprocessClicked, onStopProcessing }: Props) {
    const isProcessing = report.status === 'processing' || report.status === 'preprocessing';
    const [editPopupOpen, setEditPopupOpen] = useState(false);
    const [exportPopupOpen, setExportPopupOpen] = useState(false);
    const [isExporting, setIsExporting] = useState(false);

    const onEditDetailsClick = () => {
        setEditPopupOpen(true);
    };

    const onExportClicked = () => {
        setExportPopupOpen(true);
    }

    return (
        <>
        <Card className="min-w-70 max-w-257 w-full flex-2 px-4 py-3 m-0">
            <CardContent className="px-0 py-2 flex flex-col justify-between h-full">
                {/* Title */}
                <div className="flex justify-between items-start w-full">
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <div className="text-2xl font-bold leading-nonetruncate max-w-[28rem]">
                                {report.title}
                            </div>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>{report.title}</p>
                        </TooltipContent>
                    </Tooltip>
                </div>

                {/* Description */}
                <div className="flex items-center justify-start w-full gap-1 mt-0">
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <div className="text-sm text-muted-foreground line-clamp-3 max-w-[28rem]">
                                {report.description || "No description available"}
                            </div>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>{report.description || "No description available"}</p>
                        </TooltipContent>
                    </Tooltip>
                </div>

                <div className="flex-1" />

                {/* Bottom section */}
                <div className="flex flex-row items-end justify-between mt-4">
                    <div className="w-full">
                        {isProcessing ? (
                            <div className="flex items-center gap-2">
                                <div className="flex-1">
                                    {report.progress !== undefined && (
                                        <>
                                            <Progress value={report.progress} />
                                            <p className={`text-sm mt-1 ${statusColorMap[report.status] || "text-muted-foreground"}`}>
                                                {report.status} — {Math.round(report.progress)}%
                                            </p>
                                        </>
                                    )}
                                </div>
                                {onStopProcessing && (
                                    <Button variant="destructive" size="icon" onClick={onStopProcessing} className="shrink-0 group">
                                        <Square className="w-4 h-4 group-hover:fill-current" />
                                    </Button>
                                )}
                            </div>
                        ) : (
                            <>
                                <p className="text-sm text-muted-foreground">
                                    Created: {new Date(report.created_at).toLocaleDateString()} at{" "}
                                    {new Date(report.created_at).toLocaleTimeString()}
                                </p>
                                <p className={`text-[10px] mt-0 ${statusColorMap[report.status] || "text-muted-foreground"}`}>
                                    Status: {report.status}
                                </p>
                            </>
                        )}
                    </div>

                    {/* Menu Button */}
                    {(report.status === 'completed' || report.status === 'cancelled') && (
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="ml-2">
                                    <MoreHorizontal className="w-5 h-5" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={onEditDetailsClick}> Edit details</DropdownMenuItem>
                                <DropdownMenuItem onClick={onReprocessClicked}>Reprocess</DropdownMenuItem>
                                <DropdownMenuItem onClick={onExportClicked}>Export/Share</DropdownMenuItem>
                                <DropdownMenuItem className="text-red-600">Delete</DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
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
        <ExportPopup
            open={exportPopupOpen}
            onOpenChange={setExportPopupOpen}
            reportId={report.report_id}
            drzBackendApi="https://lets.try.this"
            isExporting={isExporting}
            onExportingChange={setIsExporting}
        />
        </>
    );
}
