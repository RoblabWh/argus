import { Boxes, Loader2, CircleCheck, CircleAlert } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { usePollColmapStatus } from "@/hooks/usePollColmapStatus";
import { useSseActive } from "@/hooks/useReportEvents";

interface Props {
    reportId: number;
}

/**
 * COLMAP 3D reconstruction status.
 *
 * COLMAP runs as a separate fire-and-forget job dispatched *after* mapping finishes, so the
 * main report status reaches "completed" while COLMAP is still running. This indicator polls
 * its own endpoint (Redis-backed status + disk-backed `has_reconstruction`) so it recovers the
 * correct state on a page reload, and is intentionally separate from the mapping progress bar.
 *
 * Renders nothing when COLMAP was never started for this report (status "none").
 */
export function ColmapStatusIndicator({ reportId }: Props) {
    const sseActive = useSseActive();
    const { data } = usePollColmapStatus(reportId, true, sseActive);

    if (!data || data.status === "none") return null;

    const { status, progress, message } = data;

    if (status === "queued" || status === "running") {
        return (
            <div className="mt-3 w-full border-t pt-2">
                <div className="flex items-center gap-1.5 text-xs font-medium">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600 dark:text-blue-400" />
                    <span>3D reconstruction</span>
                </div>
                <Progress value={progress} className="mt-1.5 h-1.5" />
                <p className="text-[11px] text-muted-foreground mt-1">
                    {message || status} — {Math.round(progress)}%
                </p>
            </div>
        );
    }

    if (status === "completed") {
        return (
            <div className="mt-3 w-full border-t pt-2">
                <div className="flex items-center gap-1.5 text-xs font-medium text-green-600 dark:text-green-400">
                    <CircleCheck className="w-3.5 h-3.5" />
                    <span>3D reconstruction ready</span>
                    <Boxes className="w-3.5 h-3.5 opacity-70" />
                </div>
                {message && (
                    <p className="text-[11px] text-muted-foreground mt-1">{message}</p>
                )}
            </div>
        );
    }

    // status === "error"
    return (
        <div className="mt-3 w-full border-t pt-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-red-600 dark:text-red-400">
                <CircleAlert className="w-3.5 h-3.5" />
                <span>3D reconstruction failed</span>
            </div>
            {message && (
                <p className="text-[11px] text-muted-foreground mt-1">{message}</p>
            )}
        </div>
    );
}
