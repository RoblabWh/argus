import { useQuery } from "@tanstack/react-query";
import { getWebODMAvailable } from "@/api";

export const useWebODM = () =>
  useQuery({
    queryKey: ["webodm"],
    queryFn: () => getWebODMAvailable(),
  });
