import React, { useEffect, useState } from "react";
import type { Report } from "@/types/report";
import { UploadArea } from "@/components/report/upload/UploadArea";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress"; // From shadcn
import { useStartReportProcess } from "@/hooks/useStartProcessing"
import type { ProcessingSettings } from "@/types/processing";
import { Toaster } from "@/components/ui/sonner"
import { toast } from "sonner"; // Assuming you have sonner for notifications
import { useQueryClient } from "@tanstack/react-query"; // Adjust the import based on your project structure
import { MappingSettingsCard } from "@/components/report/upload/MappingSettingsCard"; // Import the new settings card
import { Separator } from "@/components/ui/separator";
interface Props {
    report: Report;
    onProcessingStarted?: () => void; // Optional callback when processing starts
}
export function Upload({ report, onProcessingStarted }: Props) {
  const startProcessingMutation = useStartReportProcess(report.report_id);
  const queryClient = useQueryClient();


const handleStartProcessing = () => {
    const settings: ProcessingSettings = {
      preprocessing: true,
      processing: true,
      keep_weather: false,
      odm_orthophoto: true,
      odm_full: false,
      reprocess_all: false,
    };

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
            onClick: () => handleStartProcessing(),
          },
        });
      },
    });
    
  };
  console.log("Upload component rendered with report:", report);

  return (
    <div className="w-full ">
              <Toaster />

       <MappingSettingsCard
          weatherAvailable={false}
          imagesContainAltitude={false}
          handleStartProcessing={handleStartProcessing}
          processButtonActive={startProcessingMutation.isPending || report.status === "processing" || report.status === "preprocessing" || report.status === "queued"}
          status={report.status}
          progress={report.progress}
        />
      <div className="mt-4">

      <Separator orientation={"horizontal"} className=" my-8" />

      {/* <Button
          className="mt-4"
          onClick={handleStartProcessing}
          disabled={
            startProcessingMutation.isPending ||
            report.status === "processing" ||
            report.status === "preprocessing" ||
            report.status === "queued" 
          }
        >
          {startProcessingMutation.isPending ? "Starting..." : "Start Processing"}
        </Button> */}
      </div>





      <UploadArea report={report} />
      

      <div className="text-sm text-muted-foreground mt-4">
        {/* Print every property of the report object */}
        <pre>{JSON.stringify(report, null, 2)}</pre>
      </div>
      
    </div>
  );
}
