import { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import type { Report } from '@/types/report';
import { useReport } from '@/hooks/reportHooks';
import { usePollReportStatus } from '@/hooks/usePollReportStatus';
import { useMaps } from '@/hooks/useMaps';
import { Upload } from '@/components/report/Upload';
import { MappingReport } from '@/components/report/MappingReport';

export default function ReportOverview() {
  const { report_id } = useParams<{ report_id: string }>();
  const { setBreadcrumbs } = useBreadcrumbs();
  const { data: initialReport, isLoading, error, refetch: refetchFullReport } = useReport(Number(report_id));
  // const { data: maps, refetch: refetchMaps } = useMaps(Number(report_id));
  const prevStatusRef = useRef<string | null>(null);


  const [liveReport, setLiveReport] = useState<Report | null>(null);
  const [shouldPoll, setShouldPoll] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const isMappingMode = liveReport?.status === "processing" || liveReport?.status === "completed" && !isEditing;



  // Start polling if the report is processing or preprocessing
  useEffect(() => {
    if (initialReport) {
      setBreadcrumbs([
        { label: "Overview", href: "/overview" },
        { label: "Group", href: "/group/" + initialReport.group_id },
        { label: initialReport.title || "Unknown Report", href: `/report/${initialReport.report_id}` },
      ]);
    }
    if (
      initialReport &&
      (initialReport.status === "processing" ||
        initialReport.status === "preprocessing" ||
        initialReport.status === "queued")
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
      const prevStatus = prevStatusRef.current;
      const newStatus = polledData.status;
      setLiveReport((prev) => {
        if (!prev) return polledData;
        return {
          ...prev,
          status: polledData.status,
          progress: polledData.progress,
        };
      });

      if (prevStatus !== newStatus) {
        console.log("Detected status change. Refetching full report...");
        refetchFullReport();
      }
      if (prevStatus === "processing" && newStatus === "processing") {
        if (polledData.progress !== undefined && prevStatusRef.current !== undefined) {
          if (polledData.progress !== prevStatusRef.current.progress) {
            console.log("Detected progress change. Refetching maps...");
            //replace maps with the new data
            refetchFullReport();
          }
        }
      }

      // Stop polling if status changes to completed or failed
      if (
        polledData.status !== "processing" &&
        polledData.status !== "preprocessing" &&
        polledData.status !== "queued"
      ) {
        setShouldPoll(false);
      }
      console.log(`Polled report status: ${newStatus}, old status: ${prevStatus}`);

      prevStatusRef.current = newStatus;

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
    <>
      {isMappingMode ? (
        <div className="w-full h-[calc(100vh-54px)] overflow-hidden">
          {renderReportContent(liveReport!)}
        </div>
      ) : (
        <div className="container mx-auto px-4 pt-4">
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
        </div>)
      }
    </>
  );
}

