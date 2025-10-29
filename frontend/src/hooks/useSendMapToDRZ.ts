import { useMutation } from "@tanstack/react-query";
import { sendMapToDrz } from "@/api";

type Vars = { reportId: number; mapId: number; layerName: string };

export function useSendMapToDrz() {
  return useMutation<{success: boolean; message: string}, Error, Vars>({
    mutationFn: ({ reportId, mapId, layerName }) =>
      sendMapToDrz(reportId, { map_id: mapId, layer_name: layerName }),
  });
}