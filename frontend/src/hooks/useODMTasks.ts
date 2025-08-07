import { useQuery } from "@tanstack/react-query";
import { getWebODMTasks } from "@/api";

export function useWebODMTasks(projectId?: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ["webodm-tasks", projectId],
    queryFn: () => {
      if (!projectId) throw new Error("Missing projectId");
      return getWebODMTasks(projectId);
    },
    enabled: !!projectId && enabled, // only run when both are valid
    staleTime: 1000 * 60 * 5, // cache for 5 minutes
  });
}