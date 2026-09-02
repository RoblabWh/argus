import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sendKeyframeToDrz } from "@/api";
import type { KeyframeShareRequest } from "@/types/reconstruction";

type Vars = { reportId: number; index: number; body: KeyframeShareRequest };

export function useSendKeyframeToDrz() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ reportId, index, body }: Vars) => sendKeyframeToDrz(reportId, index, body),
    onSuccess: (_data, { reportId }) => {
      // The stored coordinate comes back with the results, so the popup pre-fills next time
      queryClient.invalidateQueries({ queryKey: ["reconstruction-results", reportId] });
    },
  });
}
