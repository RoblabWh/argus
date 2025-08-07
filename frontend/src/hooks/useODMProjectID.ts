import { useQuery } from "@tanstack/react-query";
import { getODMProjectID } from "@/api";

export function useODMProjectID(reportId: number, options?: any) {
    return useQuery({
    queryKey: ["odm-project-id", reportId],
    queryFn: () => getODMProjectID(reportId),
    ...options,
  });
}
