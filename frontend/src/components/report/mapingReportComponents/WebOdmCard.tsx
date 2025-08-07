import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ExternalLink } from "lucide-react";
import { useWebODMTasks } from "@/hooks/useODMTasks";
import { useODMProjectID } from "@/hooks/useODMProjectID";
import { createLucideIcon } from 'lucide-react';
import type { IconNode } from 'lucide-react';

const iconNode: IconNode = [
    ["circle", { cx: "6.25", cy: "6.25", r: "4.25" }],
    ["circle", { cx: "17.75", cy: "6.25", r: "4.25" }],
    ["circle", { cx: "6.25", cy: "17.75", r: "4.25" }],
    ["circle", { cx: "17.75", cy: "17.75", r: "4.25" }],
    ["line", { x1: "9.5", y1: "9.5", x2: "14.5", y2: "14.5" }],
    ["line", { x1: "14.5", y1: "9.5", x2: "9.5", y2: "14.5" }]
];

const WebODMLogo = createLucideIcon("webodm-logo", iconNode);

export { WebODMLogo };

type Props = {
    isWebODMAvailable: boolean;
    webODMURL?: string;
    webODMProjectID?: string | null;
    reportID?: number;
    progress?: number;
};

export function WebOdmCard({ isWebODMAvailable, webODMURL, webODMProjectID, reportID, progress }: Props) {
    const [activeProjectID, setActiveProjectID] = useState<string | null | undefined>(webODMProjectID);

    // Step 1: Try to fetch project ID from server if missing
    const { data: webODMProjectIDData, refetch: refetchProjectID } = useODMProjectID(reportID, {
        enabled: !webODMProjectID && reportID !== undefined,
    });

    // Step 2: Update state when fetched
    useEffect(() => {
        if (webODMProjectIDData) {
            setActiveProjectID(webODMProjectIDData);
        }
    }, [webODMProjectIDData]);

    // Step 3: Fetch tasks using final project ID
    const {
        data: odmTasks,
        isLoading,
        error,
        refetch: refetchTasks,
    } = useWebODMTasks(activeProjectID, isWebODMAvailable);

    // Step 4: Re-fetch project ID on progress change, if needed
    useEffect(() => {
        if (!activeProjectID && progress !== undefined) {
            refetchProjectID();
        }
    }, [progress]);

    // Step 5: Optional - re-fetch tasks if progress updates while project ID is valid
    useEffect(() => {
        if (activeProjectID && progress !== undefined) {
            refetchTasks();
        }
    }, [progress]);

    //sort tasks by created_at descending
    odmTasks?.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    console.log("WebODM Tasks:", odmTasks);


    return (
        <Card className={`${odmTasks?.length > 0 ? "flex-2" : "flex-1"} min-w-42 max-w-320 relative overflow-hidden pb-3`}>
            {/* Background UAV Icon */}
            <WebODMLogo className="absolute right-2 top-2 w-22 h-22 opacity-100 text-muted-foreground dark:text-white z-0 pointer-events-none" />

            {/* Gradient Overlay */}
            <div className="absolute w-40 h-30 right-0 top-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/75 to-white/55 dark:from-gray-900/100 dark:via-gray-900/89 dark:to-gray-900/70" />

            <CardContent className="px-4 pt-1 flex flex-col items-start space-y-1 relative z-10">
                <div className="flex justify-start items-start w-full">
                    <div className="text-xl font-bold leading-none">WebODM</div>
                    {isWebODMAvailable && (
                        <Button
                            variant="ghost"
                            size="icon"
                            className="w-5 h-5 p-0 ml-1 "
                            onClick={() => {
                                window.open(`${webODMURL}/dashboard/`, "_blank");
                            }}
                        >
                            <ExternalLink className="w-3 h-3" />
                        </Button>
                    )}
                </div>
                <div className={` pt-0 text-muted-foreground text-xs w-full`}>
                    <p className="break-words text-xs pb-1 w-[calc(100%-20px)]">

                        {webODMProjectID ? `project id ${webODMProjectID}` : `no existing project`}
                    </p>

                    {isLoading && <p>Loading tasks...</p>}
                    {error && <p className="text-red-500">Failed to load tasks</p>}
                    {odmTasks && odmTasks.length > 0 ? (
                        <div className="flex flex-col gap-[0.5px] max-h-20 overflow-y-auto w-full pr-2">
                            {odmTasks.map((task, index) => (
                                <div key={task.id || index} className="flex items-center justify-between">
                                    <Tooltip>
                                        <TooltipTrigger className="truncate max-w-[calc(100%-4rem)] text-blue-600 dark:text-blue-500 hover:underline ">
                                            <a target="_blank" href={task.url_to_task} >{task.name}</a>
                                        </TooltipTrigger>
                                        <TooltipContent>
                                            <p className="text-sm">{task.name}</p>
                                        </TooltipContent>
                                    </Tooltip>
                                    {miniWebODMStatusTag(task.status)}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-muted-foreground italic">No tasks found</p>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}


function miniWebODMStatusTag(status: number) {
    const statusColors: Record<number, string> = {
        20: "bg-yellow-200 text-yellow-800 dark:bg-yellow-500 dark:text-yellow-100",
        30: "bg-red-200 text-red-800 dark:bg-red-800 dark:text-red-100",
        40: "bg-green-200 text-green-800 dark:bg-green-600 dark:text-green-100",
    };
    const statusText: Record<number, string> = {
        10: "Queued",
        20: "Running",
        30: "Failed",
        40: "Completed",
        50: "Cancelled",
    };

    return (
        <Badge variant="outline" className={`text-[0.6rem] h-3 p-1 ${statusColors[status] || "bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-100"}`}>
            {statusText[status] || "Unknown"}
        </Badge>
    );
}
