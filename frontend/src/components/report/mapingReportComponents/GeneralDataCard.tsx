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
import { MoreHorizontal } from "lucide-react";
import type { Report } from '@/types/report';

interface Props {
    report: Report;
    onReprocessClicked: () => void;
}

export function GeneralDataCard({ report, onReprocessClicked }: Props) {
    const isProcessing = report.status === 'processing' || report.status === 'preprocessing';

    const onEditDetailsClick = () => {
        // Handle edit details click
        console.log("Edit details clicked");
    };
    
    return (
        <Card className="min-w-70 max-w-257 w-full flex-2 px-4 py-3">
            <CardContent className="p-0 flex flex-col justify-between h-full">
                {/* Title */}
                <div className="flex justify-between items-start w-full">
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <div className="text-xl font-semibold truncate max-w-[28rem]">
                                {report.title}
                            </div>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>{report.title}</p>
                        </TooltipContent>
                    </Tooltip>
                </div>

                {/* Description */}
                <div className="flex items-center justify-start w-full gap-1 mt-2">
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <div className="text-sm text-muted-foreground line-clamp-3 max-w-[28rem] cursor-help">
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
                            <>
                                {report.progress !== undefined && (
                                    <>
                                        <Progress value={report.progress} />
                                        <p className="text-sm text-muted-foreground mt-1">
                                            {report.status} — {Math.round(report.progress)}%
                                        </p>
                                    </>
                                )}
                            </>
                        ) : (
                            <>
                                <p className="text-sm text-muted-foreground">
                                    Created: {new Date(report.created_at).toLocaleDateString()} at{" "}
                                    {new Date(report.created_at).toLocaleTimeString()}
                                </p>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Status: {report.status}
                                </p>
                            </>
                        )}
                    </div>

                    {/* Menu Button */}
                    {report.status === 'completed' && (
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="ml-2">
                                    <MoreHorizontal className="w-5 h-5" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={onEditDetailsClick}> Edit details</DropdownMenuItem>
                                <DropdownMenuItem onClick={onReprocessClicked}>Reprocess</DropdownMenuItem>
                                <DropdownMenuItem>Export</DropdownMenuItem>
                                <DropdownMenuItem className="text-red-600">Delete</DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
