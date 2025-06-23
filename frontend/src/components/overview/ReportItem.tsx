import { Badge } from "@/components/ui/badge";
import type { Report } from "@/types";


interface Props {
  report: Report;
}

const statusColor: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  processing: "bg-blue-100 text-blue-800",
  complete: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const defaultColor = "bg-gray-100 text-gray-800";

export function ReportItem({ report }: Props) {
  const colorClass = statusColor[report.status ?? ""] ?? defaultColor;

  return (
    <div className="flex justify-between items-start border rounded-md p-3 hover:bg-muted transition-colors">
      <div className="space-y-1">
        <p className="font-medium">{report.title}</p>
        {report.description && (
          <p className="text-sm text-muted-foreground">{report.description}</p>
        )}
        <p className="text-xs text-muted-foreground">
          Created: {new Date(report.created_at).toLocaleString()}
        </p>
      </div>
      <Badge className={`${colorClass} text-sm mt-1`}>
        {report.status ?? "unknown"}
      </Badge>
    </div>
  );
}
