import React, { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Progress } from '@/components/ui/progress';
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
    Bot,
    ChevronDown,
    ChevronUp
} from "lucide-react";
import type { MappingReport } from "@/types/report";
import {
    useStartAutoDescription,
    useAutoDescriptionPolling
} from "@/hooks/autoDescriptionHooks";

type Props = {
    reportID: number;
    description: string | undefined;
    onGenerateDescription?: () => void;
};

export function AutoDescriptionCard({ reportID, description }: Props) {
    const [polling, setPolling] = useState(true);
    const [expanded, setExpanded] = useState(false);
    const [descriptionText, setDescriptionText] = React.useState(description || "");

    const { mutate: start } = useStartAutoDescription(reportID);
    const { data, isLoading: isPolling } = useAutoDescriptionPolling(reportID, polling);

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
        start(undefined, {
            onSuccess: () => { setPolling(true); toast.success("Started AI description."); },
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
                    className={`relative text-xs text-muted-foreground transition-all ${expanded ? "max-h-none" : "max-h-30 overflow-hidden"
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
                    <Button
                        variant="outline"
                        className="mt-2"
                        onClick={() => {
                            handleStart();
                        }}
                    >
                        {descriptionText.length > 150 ? "Regenerate Description" : "Generate Description"}
                    </Button>
                )}
            </CardContent>
        </Card>
    );
}
