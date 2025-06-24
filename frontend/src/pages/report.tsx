import React from 'react';
import { useParams } from 'react-router-dom';
import type { Report } from '@/types/report';
import { useReport } from '@/hooks/reportHooks';
import { Upload } from '@/components/report/Upload';
import { MappingReport } from '@/components/report/MappingReport';

export default function ReportOverview() {
    const { report_id } = useParams<{ report_id: string }>();
    const { data: report, isLoading, error } = useReport(Number(report_id));

    return (
        <div className="p-6 mx-auto min-w-800px max-w-2/3">
        <div className="flex mb-4">
            <h1 className="text-2xl font-bold mr-2">
            Report: {isLoading ? "Loading..." : report?.title ?? "Unknown"}
            </h1>
        </div>

        {/* Conditional content below the always-visible header */}
        {isLoading && <p>Loading report...</p>}
        {error && <p className="text-red-500">Error loading report: {error.message}</p>}
        {!isLoading && !error && !report && <p>No report found</p>}
        {!isLoading && !error && report && renderReportContent(report)}
        </div>
    );
}

function renderReportContent(report: Report) {
  switch (report.status) {
    case "unprocessed":
    case "preprocessing":
      return <Upload report={report} />;
    case "processing":
    case "finished":
      return <MappingReport />;
    default:
      return <p>Unknown report status: {report.status}</p>;
  }
}
