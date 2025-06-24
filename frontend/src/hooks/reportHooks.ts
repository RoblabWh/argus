import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getReport, createReport } from "@/api"; 

const useReport = (id: number) => 
    useQuery({
    queryKey: ["report", id],
    queryFn: () => getReport(id),
    enabled: !!id,
  });

const useCreateReport = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createReport,
    onSuccess: () => {
      // Invalidate and refetch the groups query to reflect the new report
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });
};

export { useReport, useCreateReport };