// src/hooks/useGroups.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getGroups, getGroup , getGroupReports, createGroup, deleteGroup, editGroup } from "@/api";



const useGroups = () =>
  useQuery({
    queryKey: ["groups"],
    queryFn: getGroups,
    staleTime: 1000 * 60 * 5,
  });


const useGroup = (id: number) =>
  useQuery({
    queryKey: ["group", id],
    queryFn: () => getGroup(id),
    enabled: !!id,
  });


const useGroupReports = (groupId: number) =>
  useQuery({
    queryKey: ["groupReports", groupId],
    queryFn: () => getGroupReports(groupId),
    enabled: !!groupId,
  });


const useCreateGroup = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createGroup,
    onSuccess: () => {
      // Invalidate and refetch the groups query to reflect the new group
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });
};

const useDeleteGroup = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteGroup,
    onSuccess: () => {
      // Invalidate and refetch the groups query to reflect the deletion
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });
};

const useEditGroup = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: editGroup,
    onSuccess: () => {
      // Invalidate and refetch the groups query to reflect the update
      queryClient.invalidateQueries({ queryKey: ["group"] });
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });
};

export {
  useGroups,
  useGroup,
  useGroupReports,
  useCreateGroup, 
  useDeleteGroup,
  useEditGroup,
};