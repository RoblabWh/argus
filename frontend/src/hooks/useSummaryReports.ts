// src/hooks/useGroups.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSummaryReports } from "@/api";


export const useSummaryReports = (group_id: number) =>
  useQuery({
    queryKey: ["groups", group_id, "summary"],
    queryFn: () => getSummaryReports(group_id),
    staleTime: 1000 * 60 * 5,
  });