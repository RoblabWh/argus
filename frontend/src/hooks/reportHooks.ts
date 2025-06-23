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
      // Invalidate and refetch the reports query to reflect the new report
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
  });
};

export { useReport, useCreateReport };