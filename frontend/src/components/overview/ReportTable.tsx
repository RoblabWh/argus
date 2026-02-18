import { useState, useMemo } from "react"
import { Input } from "@/components/ui/input"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow
} from "@/components/ui/table"
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { MoreHorizontal, ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react"
import { format } from "date-fns"
import { useDeleteReport } from "@/hooks/reportHooks"
import { EditReportPopup } from "@/components/report/EditReportPopup"
import { ExportPopup } from "@/components/report/mappingReportComponents/ShareMapImagesPopup"
import { MoveReportPopup } from "@/components/overview/MoveReportPopup"

import type { Report } from "@/types/report"

type Props = {
    reports: Report[]
}

type SortField = "report_id" | "title" | "flight_date" | "created_at"
type SortDirection = "asc" | "desc"

export function ReportTable({ reports }: Props) {
    const [search, setSearch] = useState("")
    const { mutate: deleteReport } = useDeleteReport()
    const [sortConfig, setSortConfig] = useState<{ field: SortField, direction: SortDirection }>({
        field: "report_id",
        direction: "asc"
    })

    // Popup state — single instance shared across all rows
    const [editTarget, setEditTarget] = useState<Report | null>(null)
    const [exportTargetId, setExportTargetId] = useState<number | null>(null)
    const [isExporting, setIsExporting] = useState(false)
    const [moveTarget, setMoveTarget] = useState<Report | null>(null)

    const handleSort = (field: SortField) => {
        setSortConfig((prev) => ({
            field,
            direction: prev.field === field && prev.direction === "asc" ? "desc" : "asc"
        }))
    }

    const sortedReports = useMemo(() => {
        const filtered = reports.filter((report) =>
            report.title.toLowerCase().includes(search.toLowerCase())
        )

        return filtered.sort((a, b) => {
            const { field, direction } = sortConfig

            let aValue: string | number | Date = ""
            let bValue: string | number | Date = ""

            if (field === "report_id") {
                aValue = parseInt(String(a.report_id))
                bValue = parseInt(String(b.report_id))
            } else if (field === "title") {
                aValue = a.title.toLowerCase()
                bValue = b.title.toLowerCase()
            } else if (field === "flight_date") {
                aValue = a.mapping_report?.flight_timestamp ? new Date(a.mapping_report.flight_timestamp) : new Date(0)
                bValue = b.mapping_report?.flight_timestamp ? new Date(b.mapping_report.flight_timestamp) : new Date(0)
            } else if (field === "created_at") {
                aValue = new Date(new Date(a.created_at))
                bValue = new Date(new Date(b.created_at))
            }

            if (aValue < bValue) return direction === "asc" ? -1 : 1
            if (aValue > bValue) return direction === "asc" ? 1 : -1
            return 0
        })
    }, [search, reports, sortConfig])


    const renderSortIcon = (field: SortField) => {
        if (sortConfig.field !== field) return <ChevronsUpDown className="inline w-4 h-4 ml-1 text-muted-foreground opacity-60" />
        return sortConfig.direction === "asc" ? <ChevronUp className="inline w-4 h-4 ml-1" /> : <ChevronDown className="inline w-4 h-4 ml-1" />
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

        return (
            <Badge className={statusMap[status] || defaultColor}>
                {status.charAt(0).toUpperCase() + status.slice(1)}
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

    return (
        <div className="space-y-4" onClick={(e) => e.stopPropagation()}>
            <Input
                placeholder="Search by title..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full md:w-1/2"
            />

            <div className="rounded-xl border shadow-sm overflow-hidden" onClick={(e) => e.stopPropagation()}>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="whitespace-nowrap w-0 cursor-pointer"
                                onClick={() => handleSort("report_id")}
                            >ID {renderSortIcon("report_id")}</TableHead>
                            <TableHead
                                className="w-full max-w-0"
                                onClick={() => handleSort("title")}
                            >
                                <div className="flex items-center cursor-pointer">
                                    Title {renderSortIcon("title")}
                                </div>
                            </TableHead>
                            <TableHead className="whitespace-nowrap w-0 cursor-pointer">
                                Description
                            </TableHead>
                            <TableHead className="whitespace-nowrap w-0 cursor-pointer" onClick={() => handleSort("flight_date")}>
                                Flight Date {renderSortIcon("flight_date")}
                            </TableHead>
                            <TableHead className="whitespace-nowrap w-0 cursor-pointer" onClick={() => handleSort("created_at")}>
                                Created At {renderSortIcon("created_at")}
                            </TableHead>
                            <TableHead className="whitespace-nowrap w-0">
                                Status
                            </TableHead>
                            <TableHead className="text-right whitespace-nowrap w-0">

                            </TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {sortedReports.map((report) => (
                            <TableRow key={report.report_id} onClick={() => window.location.href = `/report/${report.report_id}`} className="cursor-pointer hover:bg-muted transition-colors">
                                <TableCell className="whitespace-nowrap w-0">{report.report_id}</TableCell>

                                <TableCell className="w-full max-w-0">
                                    <span
                                        className="truncate block"
                                        title={report.title}
                                    >
                                        {report.title}
                                    </span>
                                </TableCell>

                                <TableCell className="whitespace-nowrap w-0 max-w-0">
                                    <span className="truncate block"
                                        title={report.description || "No description"}>
                                        {report.description || <span className="text-muted-foreground italic">No description</span>}
                                    </span>
                                </TableCell>

                                <TableCell className="whitespace-nowrap w-0">
                                    {report.mapping_report?.flight_timestamp
                                        ? format(new Date(report.mapping_report.flight_timestamp), "yyyy-MM-dd HH:mm")
                                        : <span className="text-muted-foreground italic">Pending</span>}
                                </TableCell>

                                <TableCell className="whitespace-nowrap w-0">
                                    {report.created_at
                                        ? format(new Date(report.created_at), "yyyy-MM-dd HH:mm")
                                        : <span className="text-muted-foreground italic">Unknown</span>}
                                </TableCell>

                                <TableCell className="text-right whitespace-nowrap w-0">
                                    {getStatusBadge(report.status)}
                                </TableCell>
                                <TableCell className="text-right">
                                    <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                            <Button variant="ghost" size="icon">
                                                <MoreHorizontal className="h-4 w-4" />
                                            </Button>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end">
                                            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); setEditTarget(report); }}>Edit</DropdownMenuItem>
                                            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); setMoveTarget(report); }}>Move</DropdownMenuItem>
                                            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); setExportTargetId(report.report_id); }}>Export</DropdownMenuItem>
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

            {editTarget && (
                <EditReportPopup
                    open={!!editTarget}
                    onOpenChange={(open) => { if (!open) setEditTarget(null); }}
                    reportId={editTarget.report_id}
                    initialTitle={editTarget.title}
                    initialDescription={editTarget.description}
                />
            )}

            {moveTarget && (
                <MoveReportPopup
                    open={!!moveTarget}
                    onOpenChange={(open) => { if (!open) setMoveTarget(null); }}
                    reportId={moveTarget.report_id}
                    reportTitle={moveTarget.title}
                    currentGroupId={moveTarget.group_id ?? 0}
                />
            )}

            {exportTargetId != null && (
                <ExportPopup
                    open={exportTargetId != null}
                    onOpenChange={(open) => { if (!open) setExportTargetId(null); }}
                    reportId={exportTargetId}
                    isExporting={isExporting}
                    onExportingChange={setIsExporting}
                />
            )}
        </div>
    )
}