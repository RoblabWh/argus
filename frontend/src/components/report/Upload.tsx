import React, { useEffect, useState } from "react";
import type { Report } from "@/types/report";
import type { ProcessingSettings } from "@/types/processing";
import type { Image, UploadFile } from "@/types/image";
import type { Weather } from "@/types/weather";
import { UploadArea } from "@/components/report/upload/UploadArea";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress"; // From shadcn
import { useStartReportProcess } from "@/hooks/useStartProcessing"
import { Toaster } from "@/components/ui/sonner"
import { toast } from "sonner"; // Assuming you have sonner for notifications
import { useQueryClient } from "@tanstack/react-query"; // Adjust the import based on your project structure
import { MappingSettingsCard } from "@/components/report/upload/MappingSettingsCard"; // Import the new settings card
import { Separator } from "@/components/ui/separator";
import { useWebODM } from '@/hooks/useWebODM';


interface Props {
  report: Report;
  onProcessingStarted?: () => void; // Optional callback when processing starts
  isEditing?: boolean; // Optional prop to control editing state
  setIsEditing?: (isEditing: boolean) => void; // Optional setter for editing state
}


function checkWeatherAvailability(report: Report): boolean {
  const mapping_report = report.mapping_report;
  if (!mapping_report || mapping_report === undefined) return false;
  const weather = mapping_report.weather;
  if (!weather || weather === undefined || weather.length === 0) return false;
  try {
    // Check if the first weather object has a temperature property
    const temp = weather[0].temperature;
    if (temp === undefined || temp === null) return false;
  } catch (error) {
    console.error("Error checking weather availability:", error);
    return false; // If there's an error accessing the temperature, assume weather is not available
  }
  return true;
}

function checkShowManualAltitudeField(report: Report): boolean {
  const mapping_report = report.mapping_report;
  if (!mapping_report || mapping_report === undefined) return false;
  const images = mapping_report.images;
  if (!images || images === undefined || images.length === 0) return false;
  // loop over images
  for (const image of images) {
    const mapping_data = image.mapping_data;
    if (!mapping_data || mapping_data === undefined) continue;
    if (mapping_data.rel_altitude_method === "manual") return true;
    // else if (mapping_data.rel_altitude_method === "googleelevationapi") return false;
    else if (mapping_data.rel_altitude_method === "exif") continue;
  }
  return false;
}

export function Upload({ report, onProcessingStarted, isEditing, setIsEditing }: Props) {
  const startProcessingMutation = useStartReportProcess(report.report_id);
  const queryClient = useQueryClient();
  const weatherAvailable = checkWeatherAvailability(report); // Replace with actual logic to determine if weather data is available
  const [uploads, setUploads] = useState<UploadFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [showManualAltitudeField, setShowManualAltitudeField] = useState(
    checkShowManualAltitudeField(report)
  );
  const { data: webODMData } = useWebODM();
  

  useEffect(() => {
    // Recheck when uploads change
    const allImages = uploads
      .map((u) => u.imageObject)
      .filter((img): img is NonNullable<typeof img> => !!img);

    const needsManualAltitude = allImages.some((img) =>
      img.mapping_data?.rel_altitude_method === "manual"
    );

    setShowManualAltitudeField(needsManualAltitude);
  }, [uploads]);

  const handleStartProcessing = (settings: ProcessingSettings) => {

    queryClient.invalidateQueries({ queryKey: ["report", report.report_id] });

    startProcessingMutation.mutate(settings, {
      onSuccess: () => {
        console.log("Processing started successfully");
        if (onProcessingStarted) {

          onProcessingStarted(); // Call the callback if provided
          console.log("onProcessingStarted callback called");
        }
      },
      onError: (error) => {
        console.error("Error starting processing:", error);
        toast("There was an error starting the processing.", {
          description: "Please try again later.",
          duration: 5000,
          action: {
            label: "Retry",
            onClick: () => handleStartProcessing(settings), // Retry with the same settings
          },
        });
      },
    });

  };

  const cancelEditing = () => {
    setIsEditing(false);
    console.log("Editing cancelled, isEditing set to false");
  };

  console.log("Upload component rendered with report:", report);

  return (
    <div className="w-full ">
      <Toaster />

      <MappingSettingsCard
        reportId={report.report_id}
        weatherAvailable={weatherAvailable}
        showManualAltitudeField={showManualAltitudeField}
        handleStartProcessing={handleStartProcessing}
        processButtonActive={startProcessingMutation.isPending || report.status === "processing" || report.status === "preprocessing" || report.status === "queued" || isUploading}
        status={report.status}
        progress={report.progress}
        onCancelEditing={cancelEditing}
        isEditing={isEditing}
        isWebODMAvailable={webODMData?.is_available}
      />

      <div className="mt-4">

        <Separator orientation={"horizontal"} className=" my-8" />

      </div>

     <UploadArea report={report} uploads={uploads} setUploads={setUploads} setIsUploading={setIsUploading} />


      <div className="text-sm text-muted-foreground mt-4">
        {/* Print every property of the report object */}
        <pre>{JSON.stringify(report, null, 2)}</pre>
      </div>

    </div>
  );
}
