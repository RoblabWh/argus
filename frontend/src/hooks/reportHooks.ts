import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getReport, createReport, deleteReport, editReport, importReport, moveReport } from "@/api"; 

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


const useUpdateReport = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: editReport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["report"] });
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });
};


const useImportReport = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ groupId, file }: { groupId: number; file: File }) =>
      importReport(groupId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });
};

const useMoveReport = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ reportId, groupId }: { reportId: number; groupId: number }) =>
      moveReport(reportId, groupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });
};

export { useReport, useCreateReport, useDeleteReport, useUpdateReport, useImportReport, useMoveReport };