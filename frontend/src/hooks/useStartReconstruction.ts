import { useMutation, useQueryClient } from "@tanstack/react-query";
import { startReconstructionProcessing } from "@/api";
import type { ReconstructionSettings } from "@/types/reconstruction";

export function useStartReconstructionProcess(report_id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (settings: ReconstructionSettings) =>
      startReconstructionProcessing(report_id, settings),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ["report-settings", report_id] });
      queryClient.invalidateQueries({ queryKey: ["report", report_id] });
    },
  });
}
