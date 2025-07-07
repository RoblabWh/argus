import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import type { Report } from '@/types/report';
import { useReport } from '@/hooks/reportHooks';
import { usePollReportStatus } from '@/hooks/usePollReportStatus';
import { Upload } from '@/components/report/Upload';
import { MappingReport } from '@/components/report/MappingReport';

export default function ReportOverview() {
  const { report_id } = useParams<{ report_id: string }>();
  const { data: initialReport, isLoading, error } = useReport(Number(report_id));
  
  const [liveReport, setLiveReport] = useState<Report | null>(null);
  const [shouldPoll, setShouldPoll] = useState(false);
  const [isEditing, setIsEditing ] = useState(false);

  // Start polling if the report is processing or preprocessing
  useEffect(() => {
    if (
      initialReport &&
      (initialReport.status === "processing" || initialReport.status === "preprocessing")
    ) {
      setLiveReport(initialReport);
      setShouldPoll(true);
    } else if (initialReport) {
      setLiveReport(initialReport);
    }
  }, [initialReport]);

  const { data: polledData } = usePollReportStatus(
    Number(report_id),
    shouldPoll
  );

  useEffect(() => {
    if (polledData) {
      setLiveReport((prev) => {
        if (!prev) return polledData;
          return {
            ...prev,
            status: polledData.status,
            progress: polledData.progress,
          };
        });

      // Stop polling if status changes to completed or failed
      if (
        polledData.status !== "processing" &&
        polledData.status !== "preprocessing" &&
        polledData.status !== "queued" 
      ) {
        setShouldPoll(false);
      }
    }
  }, [polledData])


  const renderReportContent = (report: Report) => {
    if (isEditing) {
      console.log("Rendering Upload component for editing: isEditing " + isEditing);
      return (
        <Upload
          report={report}
          onProcessingStarted={() => {
            setShouldPoll(true);
            setIsEditing(false); // exit editing once processing starts
          }}
        />
      );
    }
    
    switch (report.status) {
      case "unprocessed":
      case "preprocessing":
      case "testcase":
      case "failed":
      case "queued":
        return (
          <Upload
            report={report}
            onProcessingStarted={() => setShouldPoll(true)}
          />
        );
      case "processing":
      case "completed":
        return (
          <MappingReport
            report={report}
            onEditClicked={() => setIsEditing(true)} // <--- Pass edit handler here
          />
        );
      default:
        return <p>Unknown report status: {report.status}</p>;
    }
  }

  return (
    <div className="p-6 mx-auto min-w-800px max-w-2/3">
      <div className="flex mb-4">
        <h1 className="text-2xl font-bold mr-2">
          Report: {isLoading ? "Loading..." : liveReport?.title ?? "Unknown"}
        </h1>
      </div>

      {/* Conditional content below the always-visible header */}
      {isLoading && <p>Loading report...</p>}
      {error && <p className="text-red-500">Error loading report: {error.message}</p>}
      {!isLoading && !error && !liveReport && <p>No report found</p>}
      {!isLoading && !error && liveReport && renderReportContent(liveReport)}
    </div>
  );
}

