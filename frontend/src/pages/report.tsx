import { useEffect, useState, useRef, use } from 'react';
import { useParams } from 'react-router-dom';
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import type { Report } from '@/types/report';
import { useReport } from '@/hooks/reportHooks';
import { usePollReportStatus } from '@/hooks/usePollReportStatus';
import { useMaps, useMapsSlim } from '@/hooks/useMaps';
import { Upload } from '@/components/report/Upload';
import { MappingReport } from '@/components/report/MappingReport';
import { m } from 'motion/react';
import { useQueryClient } from '@tanstack/react-query';

export default function ReportOverview() {
  const { report_id } = useParams<{ report_id: string }>();
  const { setBreadcrumbs } = useBreadcrumbs();
  const { data: initialReport, isLoading, error, refetch: refetchFullReport } = useReport(Number(report_id));
  const { data: mapsData, refetch: refetchMaps } = useMaps(Number(report_id), false);
  const { data: slimMapsData, refetch: refetchSlimMaps } = useMapsSlim(Number(report_id), false);
  const queryClient = useQueryClient();


  const prevStatusRef = useRef<string | null>(null);


  const [liveReport, setLiveReport] = useState<Report | null>(null);
  const [liveMaps, setLiveMaps] = useState<Map[] | null>(null);
  const [shouldPoll, setShouldPoll] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [hasRefetchedAfterStatusChange, setHasRefetchedAfterStatusChange] = useState(true);


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
    console.log("Polled data:", mapsData);
    if (mapsData) {
      setLiveMaps(mapsData);
    } else {
      setLiveMaps([]);
    }
  }, [mapsData]);

  useEffect(() => {
    console.log("Slim maps data:", slimMapsData);
    if (slimMapsData) {
      if (liveMaps) {
        const newMaps = slimMapsData.filter(slimMap => !liveMaps.some(liveMap => liveMap.id === slimMap.id));
        if (newMaps.length > 0) {
          console.log("New maps found in slim data, refetching full maps...");
          queryClient.invalidateQueries({ queryKey: ["maps", report_id] });
          refetchMaps();
          // invalidate ["maps", reportId],
          return;
        }
      }
    }
  }, [slimMapsData]);

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

      const statusChanged = prevStatus !== newStatus;

      if (statusChanged) {
        if (newStatus == "completed") {
          refetchFullReport()
        } else if (prevStatus === "preprocessing" || (prevStatus === "queued" && newStatus === "processing")) {
          console.log("========> Status changed to processing or preprocessing, refetching full report...");
          setHasRefetchedAfterStatusChange(false); // Block until we refetch
          refetchFullReport().then(() => {
            setHasRefetchedAfterStatusChange(true); // Allow rendering
          });
        }
      }


      if (prevStatus === "processing" && newStatus === "processing") {
        if (polledData.progress !== undefined && prevStatusRef.current !== undefined) {
          if (polledData.progress !== prevStatusRef.current.progress) {
            if (polledData.progress > (liveReport?.progress ?? 0)) {
              setLiveReport((prev) => ({ ...prev!, progress: polledData.progress }));
              console.log("Progress increased, refetching maps...");
              refetchSlimMaps();
            }
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
        if (liveReport?.mapping_report) {
          refetchSlimMaps();
        }
      }
      console.log(`Polled report status: ${newStatus}, old status: ${prevStatus}`);

      prevStatusRef.current = newStatus;

    }
  }, [polledData])



  const renderReportContent = (report: Report) => {
    if (isEditing || !hasRefetchedAfterStatusChange) {
      console.log("Rendering Upload component for editing: isEditing " + isEditing);
      return (
        <Upload
          report={report}
          onProcessingStarted={() => {
            setShouldPoll(true);
            setIsEditing(false); // exit editing once processing starts
          }}
          isEditing={isEditing} // Pass isEditing prop to Upload
          setIsEditing={setIsEditing} // Pass setIsEditing prop to Upload
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
            onProcessingStarted={() => { setShouldPoll(true); }}
          />
        );
      case "processing":
      case "completed":
        return (
          <MappingReport
            report={report}
            onEditClicked={() => setIsEditing(true)} // <--- Pass edit handler here
            setReport={setLiveReport}
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

