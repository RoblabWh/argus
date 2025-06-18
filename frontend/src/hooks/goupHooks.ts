// src/hooks/useGroups.ts
import { useQuery } from "@tanstack/react-query";
import { getGroups, getGroup , getGroupReports } from "@/api";



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


export { useGroups, useGroup, useGroupReports };