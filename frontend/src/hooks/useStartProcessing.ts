// src/hooks/useStartProcessing.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { startReportProcessing } from "@/api";
import type { ProcessingSettings } from "@/types/processing";
import type { Report } from "@/types/report";

export const useStartReportProcess = (reportId: number) =>
  useMutation<Report, Error, ProcessingSettings>({
    mutationFn: (settings: ProcessingSettings) =>
      startReportProcessing(reportId, settings),
  });
