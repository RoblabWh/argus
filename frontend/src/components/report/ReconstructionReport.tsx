import { useState } from "react";
import type { Report } from "@/types/report";
import { getApiUrl } from "@/api";
import { useReconstructionResults } from "@/hooks/useReconstructionResults";
import { ResponsiveResizableLayout } from "@/components/ResponsiveResizableLayout";
import { GeneralDataCard } from "@/components/report/mappingReportComponents/GeneralDataCard";
import { VideoInfoCard } from "@/components/report/reconstructionReportComponents/VideoInfoCard";
import { KeyframeListCard } from "@/components/report/reconstructionReportComponents/KeyframeListCard";
import { ReconstructionViewerTab } from "@/components/report/reconstructionReportComponents/ReconstructionViewerTab";
import { ReconstructionVideoTab } from "@/components/report/reconstructionReportComponents/ReconstructionVideoTab";
import { ReconstructionDataTab } from "@/components/report/reconstructionReportComponents/ReconstructionDataTab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toaster } from "@/components/ui/sonner";
import { Loader2 } from "lucide-react";

interface Props {
  report: Report;
  onEditClicked: () => void;
  setReport: (report: Report) => void;
}

export function ReconstructionReport({ report, onEditClicked }: Props) {
  const apiUrl = getApiUrl();
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [tab, setTab] = useState("viewer");
  const [videoSeekTime, setVideoSeekTime] = useState<number | null>(null);
  const [videoOrientation, setVideoOrientation] = useState<{ yaw: number; pitch: number } | null>(null);

  const isCompleted = report.status === "completed";
  const { data: results, isLoading } = useReconstructionResults(report.report_id, isCompleted);

  const keyframes = results?.keyframes ?? [];

  const videoUrl = report.reconstruction_report?.video_path
    ? `${apiUrl}/reports_data/${report.reconstruction_report.video_path}`
    : null;

  const handlePlayFromHere = (idx: number, orientation?: { yaw: number; pitch: number }) => {
    setVideoSeekTime(keyframes[idx]?.timestamp ?? 0);
    setVideoOrientation(orientation ?? null);  // null when triggered from sidebar (no orientation)
    setTab("video");
  };

  return (
    <>
      <Toaster />
      <ResponsiveResizableLayout
        left={
          <div className="flex flex-col gap-4 h-full">
            <div className="flex flex-wrap gap-4">
              <GeneralDataCard
                report={report}
                onReprocessClicked={onEditClicked}
                disableExport
              />
              {report.reconstruction_report && (
                <VideoInfoCard reconstructionReport={report.reconstruction_report} />
              )}
            </div>

            {/* Keyframe list takes remaining height */}
            <KeyframeListCard
              keyframes={keyframes}
              selectedIndex={selectedIndex}
              onSelect={(idx) => {
                setSelectedIndex(idx);
                setTab("viewer"); // jump to viewer when selecting from list
              }}
              onPlayFromHere={videoUrl ? handlePlayFromHere : undefined}
              apiUrl={apiUrl}
            />
          </div>
        }
        right={
          <Tabs
            value={tab}
            onValueChange={setTab}
            className="w-full relative h-full"
          >
            {/* Tab switcher — centred like the mapping report */}
            <div className="absolute left-1/2 -translate-x-1/2 top-2 z-10">
              <TabsList>
                <TabsTrigger value="viewer">Viewer</TabsTrigger>
                {videoUrl && <TabsTrigger value="video">Video</TabsTrigger>}
                <TabsTrigger value="data">Data</TabsTrigger>
              </TabsList>
            </div>

            {/* Viewer tab — forceMount keeps PSV alive when switching tabs */}
            <TabsContent
              value="viewer"
              forceMount
              className={`h-full ${tab !== "viewer" ? "hidden" : ""}`}
            >
              {isLoading ? (
                <div className="w-full h-full flex items-center justify-center text-muted-foreground gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span className="text-sm">Loading keyframes…</span>
                </div>
              ) : (
                <ReconstructionViewerTab
                  keyframes={keyframes}
                  selectedIndex={selectedIndex}
                  onNavigate={setSelectedIndex}
                  onPlayFromHere={videoUrl ? handlePlayFromHere : undefined}
                  apiUrl={apiUrl}
                />
              )}
            </TabsContent>

            {/* Video tab — forceMount keeps PSV video alive when switching tabs */}
            {videoUrl && (
              <TabsContent
                value="video"
                forceMount
                className={`h-full ${tab !== "video" ? "hidden" : ""}`}
              >
                <ReconstructionVideoTab
                  videoUrl={videoUrl}
                  seekTime={videoSeekTime}
                  orientation={videoOrientation}
                  isActive={tab === "video"}
                />
              </TabsContent>
            )}

            {/* Data tab */}
            <TabsContent value="data" className="h-full overflow-auto px-2">
              <ReconstructionDataTab report={report} results={results} />
            </TabsContent>
          </Tabs>
        }
      />
    </>
  );
}
