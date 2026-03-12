import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getCameraConfigList,
  getCameraConfig,
  updateCameraConfig,
  createCameraConfig,
} from "@/api";
import type { CameraConfig } from "@/types/cameraConfig";

export function useCameraConfigList() {
  return useQuery({
    queryKey: ["camera-configs"],
    queryFn: getCameraConfigList,
  });
}

export function useCameraConfig(modelName: string | null) {
  return useQuery({
    queryKey: ["camera-config", modelName],
    queryFn: () => getCameraConfig(modelName!),
    enabled: !!modelName,
  });
}

export function useUpdateCameraConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ modelName, config }: { modelName: string; config: CameraConfig }) =>
      updateCameraConfig(modelName, config),
    onSuccess: (_, { modelName }) => {
      queryClient.invalidateQueries({ queryKey: ["camera-configs"] });
      queryClient.invalidateQueries({ queryKey: ["camera-config", modelName] });
    },
  });
}

export function useCreateCameraConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createCameraConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["camera-configs"] });
    },
  });
}
