import React, { useEffect, useState } from "react";
import type { Report } from "@/types/report";
import { UploadArea } from "@/components/report/UploadArea";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress"; // From shadcn
import { useStartReportProcess } from "@/hooks/useStartProcessing"
import type { ProcessingSettings } from "@/types/processing";
import { Toaster } from "@/components/ui/sonner"
import { toast } from "sonner"; // Assuming you have sonner for notifications

interface Props {
    report: Report;
    onProcessingStarted?: () => void; // Optional callback when processing starts
}
export function Upload({ report, onProcessingStarted }: Props) {
  const startProcessingMutation = useStartReportProcess(report.report_id);


const handleStartProcessing = () => {
    const settings: ProcessingSettings = {
      preprocessing: true,
      processing: true,
      keep_weather: false,
      odm_orthophoto: true,
      odm_full: false,
      reprocess_all: false,
    };


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

      <h2>Upload Report</h2>
      
      <div className="mt-4">
        <h3>Processing settings</h3>
        <div>
          <label>
            <input
              type="checkbox"
              onChange={(e) => {
                // Handle checkbox change if needed
                console.log("Setting changed:", e.target.checked);
              }}
            />
            Some setting
          </label>
        </div>
      <Button
          className="mt-4"
          onClick={handleStartProcessing}
          disabled={
            startProcessingMutation.isPending ||
            report.status === "processing" ||
            report.status === "preprocessing"
          }
        >
          {startProcessingMutation.isPending ? "Starting..." : "Start Processing"}
        </Button>
      </div>

      {/* Show progress bar if processing */}
      {((report.status === "processing" ||
        report.status === "preprocessing") && report.progress !== undefined) && (
        <div>
          <Progress value={report.progress} />
          <p className="text-sm text-muted-foreground mt-1">
            {report.status} — {Math.round(report.progress)}%
          </p>
        </div>
      )}



      <UploadArea report={report} />
      

      <div className="text-sm text-muted-foreground mt-4">
        {/* Print every property of the report object */}
        <pre>{JSON.stringify(report, null, 2)}</pre>
      </div>
      
    </div>
  );
}
