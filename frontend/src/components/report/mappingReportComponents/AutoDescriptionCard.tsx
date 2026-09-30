import React, { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Progress } from '@/components/ui/progress';
import { Button } from "@/components/ui/button";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { toast } from "sonner";
import {
    Bot,
    ChevronDown,
    ChevronUp
} from "lucide-react";
import type { AutoDescriptionDetail, AutoDescriptionLanguage } from "@/types/report";
import {
    useStartAutoDescription,
    useAutoDescriptionPolling
} from "@/hooks/autoDescriptionHooks";
import { useSseActive, useSseWake } from "@/hooks/useReportEvents";

type Props = {
    reportID: number;
    description: string | undefined;
    onGenerateDescription?: () => void;
};

const detailHint: Record<AutoDescriptionDetail, string> = {
    fast: "Fast: 16 representative images (hotspots and detections first, spread over the area).",
    medium: "Medium: every second image plus all hotspot/fire images. Slower, more complete.",
    detailed: "Detailed: every image. Slowest, most complete coverage.",
};

export function AutoDescriptionCard({ reportID, description }: Props) {
    const [polling, setPolling] = useState(true);
    const [expanded, setExpanded] = useState(false);
    const [descriptionText, setDescriptionText] = React.useState(description || "");
    const [detail, setDetail] = useState<AutoDescriptionDetail>("fast");
    const [language, setLanguage] = useState<AutoDescriptionLanguage>("en");

    const sseActive = useSseActive();
    const wakeSse = useSseWake();
    const { mutate: start } = useStartAutoDescription(reportID);
    const { data, isLoading: isPolling } = useAutoDescriptionPolling(reportID, polling, sseActive);

    useEffect(() => {
        if (data?.status === "completed" || data?.status === "error") {
            setPolling(false);
            if (data.status === "completed" && data.description) {
                setDescriptionText(data.description);
                toast.success("AI description completed.");
            } else if (data.status === "error") {
                toast.error("AI description failed. Please try again.");
            }
        } else if (data?.status === "processing" || data?.status === "queued") {
            setPolling(true);
        } else {
            setPolling(false);
        }
    }, [data]);


    const handleStart = () => {
        start({ detail, language }, {
            onSuccess: () => {
                setPolling(true);
                wakeSse(); // the stream is released while a report is idle
                toast.success("Started AI description.");
            },
        });
    };

    return (
        <Card className="min-w-65 flex-2 relative overflow-hidden pb-3">
            {/* Background UAV Icon */}
            <Bot className="absolute right-2 top-1 w-24 h-24 opacity-100 text-muted-foreground dark:text-white z-0 pointer-events-none" />

            {/* Gradient Overlay */}
            {/* <div className="absolute inset-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/60 to-white/0 dark:from-gray-900/100 dark:via-gray-900/70 dark:to-gray-900/0" /> */}
            <div className="absolute w-40 h-30 right-0 top-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/75 to-white/55 dark:from-gray-900/100 dark:via-gray-900/85 dark:to-gray-900/60" />


            <CardContent className="px-4 pt-1 flex flex-col items-start space-y-1 relative z-10">
                {/* Header */}
                <div className="flex justify-between items-start w-full">
                    <div className="text-xl font-bold leading-none">AI Description</div>
                </div>

                <div
                    className={`relative whitespace-pre-line text-xs text-muted-foreground transition-all ${expanded ? "max-h-none" : "max-h-30 overflow-hidden"
                        }`}
                >
                    {!expanded && (
                        <div className="absolute w-full h-full bg-gradient-to-b from-transparent via-transparent to-white/100 dark:to-gray-900/80"></div>
                    )}
                    {descriptionText.trim() || "No description available."}
                </div>

                {descriptionText.length > 150 && (
                    <div className="w-full flex justify-end relative -top-1 pb-0 -mb-2">   


                        <button
                            onClick={() => setExpanded(!expanded)}
                            className=""
                        >
                            {!expanded ? (<ChevronDown size={16} />) : (<ChevronUp size={16} />
                            )}

                        </button>

                    </div>
                )}

                {/* (re) generate description button */}
                {polling ? (
                    <Progress className="w-full mt-2" value={data?.progress || 0} />
                ) : (
                    <div className="w-full flex flex-col mt-2">
                        <div className="w-full flex flex-row flex-wrap items-center gap-2">
                            <Select value={detail} onValueChange={(v) => setDetail(v as AutoDescriptionDetail)}>
                                <SelectTrigger className="w-[130px]" size="sm">
                                    <SelectValue placeholder="Detail" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="fast">Fast</SelectItem>
                                    <SelectItem value="medium">Medium</SelectItem>
                                    <SelectItem value="detailed">Detailed</SelectItem>
                                </SelectContent>
                            </Select>
                            <Select value={language} onValueChange={(v) => setLanguage(v as AutoDescriptionLanguage)}>
                                <SelectTrigger className="w-[110px]" size="sm">
                                    <SelectValue placeholder="Language" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="en">English</SelectItem>
                                    <SelectItem value="de">Deutsch</SelectItem>
                                </SelectContent>
                            </Select>
                            <Button variant="outline" size="sm" onClick={handleStart}>
                                {descriptionText.length > 150 ? "Regenerate" : "Generate"}
                            </Button>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1 mb-0">{detailHint[detail]}</p>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
