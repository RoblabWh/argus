import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getReport, createReport, deleteReport } from "@/api"; 

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

const useDeleteReport = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteReport,
    onSuccess: () => {
      // Invalidate and refetch the reports query to reflect the deleted report
      console.log("Report deleted successfully");
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });
};

export { useReport, useCreateReport, useDeleteReport };