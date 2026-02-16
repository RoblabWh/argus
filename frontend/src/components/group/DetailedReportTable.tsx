import { useState, useMemo, useEffect, useRef } from "react"
import { Input } from "@/components/ui/input"
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
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { MoreHorizontal, ChevronUp, ChevronDown, ChevronsUpDown, Blocks, CircleQuestionMark, Globe, CircleCheck, CircleX } from "lucide-react"
import { format } from "date-fns"
import { useDeleteReport } from "@/hooks/reportHooks"

import type { Report, ReportSummary } from "@/types/report"

type Props = {
    reports: ReportSummary[]
}

type SortField = "report_id" | "title" | "flight_timestamp" | "created_at" | "status" | "type"
type SortDirection = "asc" | "desc"

export function DetailedReportTable({ reports }: Props) {
    const { mutate: deleteReport } = useDeleteReport()
    const tableContainerRef = useRef<HTMLDivElement>(null);
    const [compactMode, setCompactMode] = useState(false);
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

    const sortedReports = useMemo(() => {
        return reports.sort((a, b) => {
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
    }, [reports, sortConfig])


    const renderSortIcon = (field: SortField) => {
        if (sortConfig.field !== field) return <ChevronsUpDown className="inline w-4 h-4 m-0 text-muted-foreground opacity-60" />
        return sortConfig.direction === "asc" ? <ChevronUp className="inline w-4 h-4 m-0" /> : <ChevronDown className="inline w-4 h-4 m-0" />
    }

    const getStatusBadge = (status: string) => {
        const statusMap: Record<string, string> = {
            queued: "bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-100",
            preprocessing: "bg-yellow-200 text-yellow-800 dark:bg-yellow-500 dark:text-yellow-100",
            processing: "bg-yellow-200 text-yellow-800 dark:bg-yellow-500 dark:text-yellow-100",
            completed: "bg-green-200 text-green-800 dark:bg-green-600 dark:text-green-100",
            error: "bg-red-200 text-red-800 dark:bg-red-600 dark:text-red-100",
            failed: "bg-red-200 text-red-800 dark:bg-red-800 dark:text-red-100",
            cancelled: "bg-orange-200 text-orange-800 dark:bg-orange-600 dark:text-orange-100",
        }
        const defaultColor = "bg-gray-100 text-gray-800";
        const content = compactMode ? status.charAt(0) : status.charAt(0).toUpperCase() + status.slice(1);
        return (
            <Badge className={statusMap[status] || defaultColor}>
                {content}
            </Badge>
        )
    }


    const handleDelete = (e: React.MouseEvent, report_id: number) => {
        e.stopPropagation();
        if (confirm("Are you sure you want to delete this report?")) {
            deleteReport(report_id, {
                onSuccess: () => {
                    // Optionally, you can add a success message or redirect
                    console.log("Report deleted successfully");
                },
                onError: (error) => {
                    console.error("Error deleting report:", error);
                    alert("Failed to delete report. Please try again.");
                },
            });
        }
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

    useEffect(() => {
        const observer = new ResizeObserver(entries => {
            const width = entries[0].contentRect.width;
            setCompactMode(width < 1200); // adjust breakpoint
        });
        if (tableContainerRef.current) observer.observe(tableContainerRef.current);
        return () => observer.disconnect();
    }, []);

    return (
        <div
            ref={tableContainerRef}
            className="space-y-4 pt-16 overflow-y-auto h-full "
            onClick={(e) => e.stopPropagation()}
        >
            <div
                className={`rounded-lg border shadow-sm overflow-x-auto ${compactMode ? "compact-table" : ""}`}
                onClick={(e) => e.stopPropagation()}
            >
                <Table className="min-w-full bg-white dark:bg-gray-900">
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-0">Type</TableHead>
                            <TableHead className="truncate-col cursor-pointer" onClick={() => handleSort("title")}>Title  {renderSortIcon("title")}</TableHead>
                            <TableHead className="truncate-col description-col">Description</TableHead>
                            <TableHead className="cursor-pointer" onClick={() => handleSort("flight_timestamp")}>Flight Date  {renderSortIcon("flight_timestamp")}</TableHead>
                            <TableHead className="cursor-pointer" onClick={() => handleSort("created_at")}>Created At  {renderSortIcon("created_at")}</TableHead>
                            <TableHead className="slim-col">{compactMode ? "Img" : "Images"}</TableHead>
                            <TableHead className="slim-col">{compactMode ? "Thrm" : "Thermal"}</TableHead>
                            <TableHead className="slim-col">{compactMode ? "Pano" : "Panoramic"}</TableHead>
                            <TableHead className="slim-col">{compactMode ? "Det" : "Detections"}</TableHead>
                            <TableHead className="cursor-pointer text-center" onClick={() => handleSort("status")}>Status  {renderSortIcon("status")}</TableHead>
                            <TableHead></TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {reports.map((report) => (
                            <TableRow key={report.report_id} onClick={() => window.location.href = `/report/${report.report_id}`} className="cursor-pointer hover:bg-muted transition-colors">
                                <TableCell className="nowrap w-0">
                                    <div className="flex items-center justify-center">
                                    {makeTooltip(selectIcon(report.type), report.type)}
                                    </div>
                                </TableCell>
                                <TableCell className="truncate-col" title={report.title}>
                                    {report.title}
                                </TableCell>
                                <TableCell className="truncate-col description-col" title={report.description || "No description"}>
                                    {report.description || <span className="italic text-muted-foreground">No description</span>}
                                </TableCell>

                                <TableCell className="nowrap w-0">
                                    {report?.flight_timestamp
                                        ? format(new Date(report.flight_timestamp), "yyyy-MM-dd HH:mm")
                                        : <span className="text-muted-foreground italic">Pending</span>}
                                </TableCell>

                                <TableCell className="nowrap w-0">
                                    {report.created_at
                                        ? format(new Date(report.created_at), "yyyy-MM-dd HH:mm")
                                        : <span className="text-muted-foreground italic">Unknown</span>}
                                </TableCell>

                                <TableCell className="nowrap w-0 text-center">
                                    {report.image_count || 0}
                                </TableCell>
                                <TableCell className="nowrap w-0 p-auto">
                                    {report.thermal_count > 0
                                        ? <CircleCheck className="text-green-500 w-4 h-4 m-auto" />
                                        : <CircleX className="text-red-500 w-4 h-4 m-auto" />
                                    }
                                </TableCell>
                                <TableCell className="nowrap w-0">
                                    {report.pano_count > 0
                                        ? <CircleCheck className="text-green-500 w-4 h-4 m-auto" />
                                        : <CircleX className="text-red-500 w-4 h-4 m-auto" />
                                    }
                                </TableCell>
                                <TableCell className="nowrap w-0">
                                    {report.detection_count > 0
                                        ? <CircleCheck className="text-green-500 w-4 h-4 m-auto" />
                                        : <CircleX className="text-red-500 w-4 h-4 m-auto" />
                                    }
                                </TableCell>
                                <TableCell className="nowrap w-0">
                                    <div className="flex items-center justify-center">
                                        {compactMode ? makeTooltip(getStatusBadge(report.status), report.status) : getStatusBadge(report.status)}
                                    </div>
                                </TableCell>

                                <TableCell className="nowrap w-0">
                                    <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                            <Button variant="ghost" size="icon">
                                                <MoreHorizontal className="h-4 w-4" />
                                            </Button>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end">
                                            <DropdownMenuItem onClick={() => console.log("Edit", report.report_id)}>Edit</DropdownMenuItem>
                                            <DropdownMenuItem onClick={() => console.log("Export", report.report_id)}>Export</DropdownMenuItem>
                                            <DropdownMenuItem
                                                variant="destructive"
                                                onClick={(e) => handleDelete(e, report.report_id)}
                                            >
                                                Delete
                                            </DropdownMenuItem>
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
                {sortedReports.length === 0 && (
                    <div className="p-4 text-center text-muted-foreground">No reports found.</div>
                )}
            </div>
        </div>
    )
}