import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getThermalMap } from "@/api";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type { TempFilters } from "@/components/report/mappingReportComponents/GalleryCardFiltered";

/**
 * Server-generated temperature overlay (GeoJSON bands + region->image table),
 * clipped to the gallery's temperature filters. The filter values are
 * debounced so the overlay follows typing without a request per keystroke;
 * keepPreviousData avoids flicker while a new clip is computed. Only fetched
 * while the map's temperature layer is switched on. Invalidated on
 * map_created SSE events (thermal data only changes with re-mapping).
 */
export function useThermalMap(reportId: number, tempFilter: TempFilters, enabled: boolean) {
    const debounced = useDebouncedValue(tempFilter, 400);
    return useQuery({
        // The gallery semantics map onto the overlay clip: "MAX >= x" means
        // the user cares about areas at least that hot (t_min), "MIN <= x"
        // bounds the shown range from above (t_max).
        queryKey: ["thermalMap", reportId, debounced.minAtLeast ?? null, debounced.maxAtMost ?? null],
        queryFn: () => getThermalMap(reportId, debounced.minAtLeast, debounced.maxAtMost),
        enabled,
        placeholderData: keepPreviousData,
    });
}
