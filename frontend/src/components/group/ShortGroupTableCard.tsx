import { useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
    ChevronFirst,
    ChevronLast,
    Image as ImageIcon,
    Map as AreaIcon,
    File,
    NotebookText,
} from "lucide-react";
import type { ReportSummary } from "@/types/report";
import { add } from "date-fns";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow
} from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "../ui/tooltip"
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import { ChevronUp, ChevronDown, ChevronsUpDown, Blocks, CircleQuestionMark, Globe, CircleCheck, CircleX } from "lucide-react"
import { format } from "date-fns"


type Props = {
    data: ReportSummary[] | undefined;
};


type SortField = "report_id" | "title" | "flight_timestamp" | "created_at" | "status" | "type"
type SortDirection = "asc" | "desc"


export function ShortGroupTableCard({ data = [] }: Props) {
    if (!data || Object.keys(data).length === 0 || data === undefined) {
        return (
            <Card className="min-w-52 max-w-103 flex-1 relative overflow-hidden ">
                <CardContent className="text-center text-muted-foreground">
                    No Reports Found.
                </CardContent>
            </Card>
        );
    }
    const compactMode = true;

    data.sort((a, b) => (a.flight_timestamp > b.flight_timestamp ? 1 : -1));
    const firstFlight = data[0];
    const hasMoreThanOneFlight = data.length > 1;

    let lastFlight = data[data.length - 1];
    for (let i = data.length - 1; i >= 0; i--) {
        if (data[i].flight_timestamp && i > 0) {
            lastFlight = data[i];
            break;
        } else if (i === 0) {
            lastFlight = data[data.length - 1]; // Fallback to last flight then with no valid timestamp
        }
    }
    const total_images = data.reduce((acc, flight) => acc + (flight.image_count || 0), 0);
    const total_maps = data.reduce((acc, flight) => acc + (flight.maps.length || 0), 0);

    const [sortConfig, setSortConfig] = useState<{ field: SortField, direction: SortDirection }>({
        field: "report_id",
        direction: "asc"
    })

    const handleSort = (field: SortField) => {
        setSortConfig((prev) => ({
            field,
            direction: prev.field === field && prev.direction === "asc" ? "desc" : "asc"
        }))
    }

        const selectIcon = (type: string) => {
        switch (type) {
            case "mapping":
                return <Blocks className="w-4 h-4" />
            case "panoramic":
                return <Globe className="w-4 h-4" />
            default:
                return <CircleQuestionMark className="w-4 h-4" />
        }
    }

    const makeTooltip = (trigger: React.ReactNode, content: string) => (
        <TooltipProvider>
            <Tooltip>
                <TooltipTrigger>{trigger}</TooltipTrigger>
                <TooltipContent>{content}</TooltipContent>
            </Tooltip>
        </TooltipProvider>
    )

    const containsThermalImages = (images: any[]) => {
        return images.some(image => image.thermal === true);
    }
    const containsPanoImages = (images: any[]) => {
        return images.some(image => image.pano === true);
    }

    const sortedReports = useMemo(() => {
        return data.sort((a, b) => {
            const { field, direction } = sortConfig

            let aValue: string | number | Date = ""
            let bValue: string | number | Date = ""

            if (field === "report_id") {
                aValue = parseInt(String(a.report_id))
                bValue = parseInt(String(b.report_id))
            } else if (field === "title") {
                aValue = a.title.toLowerCase()
                bValue = b.title.toLowerCase()
            } else if (field === "flight_timestamp") {
                aValue = a?.flight_timestamp ? new Date(a.flight_timestamp) : new Date(0)
                bValue = b?.flight_timestamp ? new Date(b.flight_timestamp) : new Date(0)
            } else if (field === "created_at") {
                aValue = new Date(new Date(a.created_at))
                bValue = new Date(new Date(b.created_at))
            } else if (field === "status") {
                aValue = a.status.toLowerCase()
                bValue = b.status.toLowerCase()
            } else if (field === "type") {
                aValue = a.type.toLowerCase()
                bValue = b.type.toLowerCase()
            }

            if (aValue < bValue) return direction === "asc" ? -1 : 1
            if (aValue > bValue) return direction === "asc" ? 1 : -1
            return 0
        })
    }, [data, sortConfig])


    const renderSortIcon = (field: SortField) => {
        if (sortConfig.field !== field) return <ChevronsUpDown className="inline w-4 h-4 m-0 text-muted-foreground opacity-60" />
        return sortConfig.direction === "asc" ? <ChevronUp className="inline w-4 h-4 m-0" /> : <ChevronDown className="inline w-4 h-4 m-0" />
    }


    return (
        <Card className="min-w-80 max-w-480 flex-3 relative overflow-hidden pb-3">
            {/* Background UAV Icon */}
            <NotebookText className="absolute right-2 top-1 w-24 h-24 opacity-100 text-muted-foreground dark:text-white z-0 pointer-events-none" />

            {/* Gradient Overlay */}
            {/* <div className="absolute inset-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/60 to-white/0 dark:from-gray-900/100 dark:via-gray-900/70 dark:to-gray-900/0" /> */}
            <div className="absolute w-40 h-30 right-0 top-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/75 to-white/55 dark:from-gray-900/100 dark:via-gray-900/85 dark:to-gray-900/60" />

            <CardContent className="px-4 pt-1 flex flex-col items-start space-y-1 relative z-10">
                {/* Header */}
                <div className="flex justify-between items-start w-full pb-2">
                    <div className="text-xl font-bold leading-none whitespace-nowrap truncate">Report(s): </div>
                </div>

                <div
                    className={`w-full max-h-104 rounded-lg border shadow-sm overflow-x-auto ${compactMode ? "compact-table" : ""}`}
                    onClick={(e) => e.stopPropagation()}
                >
                    <Table className="w-full bg-white/40 dark:bg-gray-900/40">
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-0">Type</TableHead>
                                <TableHead className="truncate-col cursor-pointer w-full" onClick={() => handleSort("title")}>Title  {renderSortIcon("title")}</TableHead>
                                <TableHead className="w-0 cursor-pointer" onClick={() => handleSort("flight_timestamp")}>Flight Date  {renderSortIcon("flight_timestamp")}</TableHead>
                                <TableHead className="slim-col">{makeTooltip("Thrm", "Thermal")}</TableHead>
                                <TableHead></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {data.map((report) => (
                                <TableRow key={report.report_id} onClick={() => window.location.href = `/report/${report.report_id}`} className="cursor-pointer hover:bg-muted transition-colors">
                                    <TableCell className="nowrap w-0">
                                        <div className="flex items-center justify-center">
                                            {makeTooltip(selectIcon(report.type), report.type)}
                                        </div>
                                    </TableCell>
                                    <TableCell className="truncate-col" title={report.title}>
                                        {report.title}
                                    </TableCell>

                                    <TableCell className="nowrap w-0 text-right">
                                        {report?.flight_timestamp
                                            ? format(new Date(report.flight_timestamp), "yyyy-MM-dd HH:mm")
                                            : <span className="text-muted-foreground italic">Pending</span>}
                                    </TableCell>
                                    <TableCell className="nowrap w-0 p-auto">
                                    {report.thermal_count > 0
                                        ? <CircleCheck className="text-green-500 w-4 h-4 m-auto" />
                                        : <CircleX className="text-red-500 w-4 h-4 m-auto" />
                                    }
                                </TableCell>

                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                    {sortedReports.length === 0 && (
                        <div className="p-4 text-center text-muted-foreground">No reports found.</div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
