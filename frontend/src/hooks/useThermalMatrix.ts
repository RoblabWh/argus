import { useQuery } from "@tanstack/react-query";
import { getThermalMatrix } from "@/api";

export const useThermalMatrix = (
  imageId?: number,
  thermal?: boolean
) => {
  return useQuery({
    queryKey: ["thermal_matrix", imageId, thermal],
    queryFn: () => getThermalMatrix(imageId!),
    enabled: !!imageId && thermal === true,
  });
};
