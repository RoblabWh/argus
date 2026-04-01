import { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import type { Report } from '@/types/report';
import type { Map as OrthoMap } from '@/types/map';
import { useReport } from '@/hooks/reportHooks';
import { usePollReportStatus } from '@/hooks/usePollReportStatus';
import { usePollReconstructionStatus } from '@/hooks/usePollReconstructionStatus';
import { useMaps, useMapsSlim } from '@/hooks/useMaps';
import { Upload } from '@/components/report/Upload';
import { MappingReport } from '@/components/report/MappingReport';
import { ReconstructionReport } from '@/components/report/ReconstructionReport';
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
  const [liveMaps, setLiveMaps] = useState<OrthoMap[] | null>(null);
  const [shouldPoll, setShouldPoll] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [hasRefetchedAfterStatusChange, setHasRefetchedAfterStatusChange] = useState(true);

  const isFullscreenMode =
    (liveReport?.status === "processing" ||
      liveReport?.status === "completed" ||
      liveReport?.status === "cancelled") &&
    !isEditing;

  // Start polling if the report is processing or queued
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

  // General report status polling (works for both mapping and reconstruction)
  const { data: polledData } = usePollReportStatus(
    Number(report_id),
    shouldPoll
  );

  // Reconstruction-specific status polling (for detailed progress messages)
  const isReconstructionType = liveReport?.type === "reconstruction_360";
  const { data: reconstructionStatus } = usePollReconstructionStatus(
    Number(report_id),
    shouldPoll && isReconstructionType
  );

  useEffect(() => {
    if (mapsData) {
      setLiveMaps(mapsData);
    } else {
      setLiveMaps([]);
    }
  }, [mapsData]);

  useEffect(() => {
    if (slimMapsData) {
      if (liveMaps) {
        const newMaps = slimMapsData.filter(
          (slimMap) => !liveMaps.some((liveMap) => liveMap.id === slimMap.id)
        );
        if (newMaps.length > 0) {
          queryClient.invalidateQueries({ queryKey: ["maps", report_id] });
          refetchMaps();
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
        if (newStatus === "completed") {
          refetchFullReport();
        } else if (prevStatus === "preprocessing" || (prevStatus === "queued" && newStatus === "processing")) {
          setHasRefetchedAfterStatusChange(false);
          refetchFullReport().then(() => {
            setHasRefetchedAfterStatusChange(true);
          });
        }
      }

      if (prevStatus === "processing" && newStatus === "processing") {
        if (polledData.progress !== undefined) {
          if (polledData.progress > (liveReport?.progress ?? 0)) {
            setLiveReport((prev) => ({ ...prev!, progress: polledData.progress }));
            // Only refetch maps for mapping reports
            if (!isReconstructionType) {
              refetchSlimMaps();
            }
          }
        }
      }

      // For reconstruction: keep polling alive while the worker is still running,
      // even if the report status has already moved past "queued"/"processing".
      const reconstructionStillRunning =
        isReconstructionType &&
        (reconstructionStatus?.status === "queued" ||
          reconstructionStatus?.status === "running");

      if (
        !reconstructionStillRunning &&
        polledData.status !== "processing" &&
        polledData.status !== "preprocessing" &&
        polledData.status !== "queued"
      ) {
        setShouldPoll(false);
        if (liveReport?.mapping_report) {
          refetchSlimMaps();
        }
      }

      prevStatusRef.current = newStatus;
    }
  }, [polledData]);

  // Use reconstruction-specific status to drive progress + completion
  useEffect(() => {
    if (!reconstructionStatus || !isReconstructionType) return;

    console.log(`[Reconstruction] ${reconstructionStatus.status} (${reconstructionStatus.progress}%) — ${reconstructionStatus.message}`);

    // Feed progress into live report state
    if (reconstructionStatus.progress !== undefined) {
      setLiveReport((prev) =>
        prev ? { ...prev, progress: reconstructionStatus.progress } : prev
      );
    }

    // Worker finished → full refetch will transition report.status to "completed"
    if (reconstructionStatus.status === "finished") {
      setShouldPoll(false);
      refetchFullReport();
    }

    // Worker errored → stop polling, mark report as failed locally
    if (reconstructionStatus.status === "error") {
      setShouldPoll(false);
      setLiveReport((prev) =>
        prev ? { ...prev, status: "failed" } : prev
      );
    }
  }, [reconstructionStatus, isReconstructionType]);


  const renderReportContent = (report: Report) => {
    if (isEditing || !hasRefetchedAfterStatusChange) {
      return (
        <Upload
          report={report}
          onProcessingStarted={() => {
            setShouldPoll(true);
            setIsEditing(false);
          }}
          isEditing={isEditing}
          setIsEditing={setIsEditing}
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
      case "cancelled":
        if (report.type === "reconstruction_360") {
          return (
            <ReconstructionReport
              report={report}
              onEditClicked={() => setIsEditing(true)}
              setReport={setLiveReport}
            />
          );
        }
        return (
          <MappingReport
            report={report}
            onEditClicked={() => setIsEditing(true)}
            setReport={setLiveReport}
          />
        );
      default:
        return <p>Unknown report status: {report.status}</p>;
    }
  };

  return (
    <>
      {isFullscreenMode ? (
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

          {isLoading && <p>Loading report...</p>}
          {error && <p className="text-red-500">Error loading report: {error.message}</p>}
          {!isLoading && !error && !liveReport && <p>No report found</p>}
          {!isLoading && !error && liveReport && renderReportContent(liveReport)}
        </div>
      )}
    </>
  );
}
