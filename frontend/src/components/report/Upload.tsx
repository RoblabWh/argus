import React, { useEffect, useState } from "react";
import type { Report } from "@/types/report";
import type { ProcessingSettings } from "@/types/processing";
import type { UploadFile } from "@/types/image";
import type { UploadSummary, ReconstructionSettings } from "@/types/reconstruction";
import { UploadArea } from "@/components/report/upload/UploadArea";
import { useStartReportProcess } from "@/hooks/useStartProcessing";
import { useStartReconstructionProcess } from "@/hooks/useStartReconstruction";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { MappingSettingsCard } from "@/components/report/upload/MappingSettingsCard";
import { ReconstructionSettingsCard } from "@/components/report/upload/ReconstructionSettingsCard";
import { Separator } from "@/components/ui/separator";
import { useWebODM } from "@/hooks/useWebODM";
import { Card, CardContent } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Settings } from "lucide-react";


interface Props {
  report: Report;
  onProcessingStarted?: () => void;
  isEditing?: boolean;
  setIsEditing?: (isEditing: boolean) => void;
  statusMessage?: string;
}


function checkWeatherAvailability(report: Report): boolean {
  const mapping_report = report.mapping_report;
  if (!mapping_report) return false;
  const weather = mapping_report.weather;
  if (!weather || weather.length === 0) return false;
  try {
    const temp = weather[0].temperature;
    if (temp === undefined || temp === null) return false;
  } catch {
    return false;
  }
  return true;
}


export function Upload({ report, onProcessingStarted, isEditing, setIsEditing, statusMessage }: Props) {
  const startMappingMutation = useStartReportProcess(report.report_id);
  const startReconstructionMutation = useStartReconstructionProcess(report.report_id);
  const queryClient = useQueryClient();
  const weatherAvailable = checkWeatherAvailability(report);
  const [uploads, setUploads] = useState<UploadFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [showManualAltitudeField, setShowManualAltitudeField] = useState(false);
  const [showFovField, setShowFovField] = useState(false);
  const [showCamPitchField, setShowCamPitchField] = useState(false);
  const [showCamOrientationField, setShowCamOrientationField] = useState(false);
  const { data: webODMData } = useWebODM();

  // Track which report type was determined (initialised from existing report type)
  const [detectedType, setDetectedType] = useState<string>(report.type);
  // Keeps button disabled after processing starts, until the view switches away
  const [processingStarted, setProcessingStarted] = useState(false);

  const handleUploadComplete = (summary: UploadSummary) => {
    if (summary.report_type !== "unchanged") {
      setDetectedType(summary.report_type);
    }
  };

  useEffect(() => {
    const allImages = uploads
      .map((u) => u.imageObject)
      .filter((img): img is NonNullable<typeof img> => !!img);

    setShowManualAltitudeField(
      allImages.some((img) => img.mapping_data?.rel_altitude_method === "manual")
    );
    setShowFovField(allImages.some((img) => img.mapping_data?.fov_method === "manual"));
    setShowCamPitchField(
      allImages.some((img) => img.mapping_data?.cam_pitch_method === "manual")
    );
    setShowCamOrientationField(
      allImages.some(
        (img) =>
          img.mapping_data?.cam_yaw_method === "uav" ||
          img.mapping_data?.cam_roll_method === "uav"
      )
    );
  }, [uploads]);

  const handleStartMappingProcessing = (settings: ProcessingSettings) => {
    queryClient.invalidateQueries({ queryKey: ["report", report.report_id] });
    queryClient.removeQueries({ queryKey: ["report-settings", report.report_id] });
    queryClient.invalidateQueries({ queryKey: ["processing-settings", report.report_id] });

    startMappingMutation.mutate(settings, {
      onSuccess: () => {
        if (onProcessingStarted) onProcessingStarted();
      },
      onError: (error) => {
        console.error("Error starting mapping processing:", error);
        toast("There was an error starting the processing.", {
          description: "Please try again later.",
          duration: 5000,
          action: {
            label: "Retry",
            onClick: () => handleStartMappingProcessing(settings),
          },
        });
      },
    });
  };

  const handleStartReconstructionProcessing = (settings: ReconstructionSettings) => {
    startReconstructionMutation.mutate(settings, {
      onSuccess: () => {
        setProcessingStarted(true);
        if (onProcessingStarted) onProcessingStarted();
      },
      onError: (error) => {
        console.error("Error starting reconstruction processing:", error);
        toast("There was an error starting the reconstruction.", {
          description: "Please try again later.",
          duration: 5000,
          action: {
            label: "Retry",
            onClick: () => handleStartReconstructionProcessing(settings),
          },
        });
      },
    });
  };

  const cancelEditing = () => {
    if (setIsEditing) setIsEditing(false);
  };

  const isMappingActive =
    startMappingMutation.isPending ||
    report.status === "processing" ||
    report.status === "preprocessing" ||
    report.status === "queued" ||
    isUploading;

  const isReconstructionActive =
    processingStarted ||
    startReconstructionMutation.isPending ||
    report.status === "processing" ||
    report.status === "queued" ||
    isUploading;

  return (
    <div className="w-full">
      <Toaster />

      {/* ── Settings section (always at top) ── */}
      {detectedType === "unset" ? (
        <Card className="w-full mb-0">
          <CardContent className="py-6 flex flex-col items-center gap-2 text-muted-foreground">
            <Settings className="w-6 h-6" />
            <p className="text-sm">Upload files to configure processing settings</p>
          </CardContent>
        </Card>
      ) : detectedType === "reconstruction_360" ? (
        <ReconstructionSettingsCard
          status={report.status}
          progress={report.progress}
          statusMessage={statusMessage}
          isEditing={isEditing}
          onCancelEditing={cancelEditing}
          handleStartProcessing={handleStartReconstructionProcessing}
          processButtonActive={isReconstructionActive}
          existingSettings={report.reconstruction_report?.processing_settings}
        />
      ) : (
        <MappingSettingsCard
          reportId={report.report_id}
          weatherAvailable={weatherAvailable}
          showManualAltitudeField={showManualAltitudeField}
          showFovField={showFovField}
          showCamPitchField={showCamPitchField}
          showCamOrientationField={showCamOrientationField}
          handleStartProcessing={handleStartMappingProcessing}
          processButtonActive={isMappingActive}
          status={report.status}
          progress={report.progress}
          onCancelEditing={cancelEditing}
          isEditing={isEditing}
          isWebODMAvailable={webODMData?.is_available}
        />
      )}

      <Separator orientation="horizontal" className="my-8" />

      {/* ── Upload area ── */}
      <UploadArea
        report={report}
        uploads={uploads}
        setUploads={setUploads}
        setIsUploading={setIsUploading}
        onUploadComplete={handleUploadComplete}
        detectedType={detectedType}
      />

      {/* ── Debug data (collapsible) ── */}
      <Accordion type="single" collapsible className="mt-8">
        <AccordionItem value="debug">
          <AccordionTrigger className="text-xs text-muted-foreground hover:no-underline">
            Debug: Report Data
          </AccordionTrigger>
          <AccordionContent>
            <pre className="text-xs overflow-auto max-h-96 bg-muted/50 rounded p-3">
              {JSON.stringify(report, null, 2)}
            </pre>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
