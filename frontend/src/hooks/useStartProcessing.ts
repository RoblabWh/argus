// src/hooks/useStartProcessing.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { startReportProcessing, stopReportProcessing } from "@/api";
import type { ProcessingSettings } from "@/types/processing";
import type { Report } from "@/types/report";

export const useStartReportProcess = (reportId: number) =>
  useMutation<Report, Error, ProcessingSettings>({
    mutationFn: (settings: ProcessingSettings) =>
      startReportProcessing(reportId, settings),
  });

export const useStopProcessing = (reportId: number) => {
  const queryClient = useQueryClient();
  return useMutation<Report, Error, void>({
    mutationFn: () => stopReportProcessing(reportId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["report", reportId] });
      queryClient.invalidateQueries({ queryKey: ["report-process", reportId] });
    },
  });
};
