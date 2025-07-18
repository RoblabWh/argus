import { useQuery } from "@tanstack/react-query";
import { getMaps } from "@/api"; 
import type { Map } from "@/types/map";

export const useMaps = (report_id: number) => 
    useQuery({
        queryKey: ["maps", report_id],
        queryFn: () => getMaps(report_id)
    });
