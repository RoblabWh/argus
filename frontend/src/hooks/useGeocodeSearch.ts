import { useQuery } from "@tanstack/react-query";
import { geocodeSearch } from "@/api";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

/**
 * Address search for the coordinate picker. The term is debounced to stay within
 * Nominatim's rate limit, and an unreachable geocoder yields an empty list rather
 * than an error — picking on the map still works offline.
 */
export function useGeocodeSearch(term: string) {
  const debounced = useDebouncedValue(term.trim(), 400);
  return useQuery({
    queryKey: ["geocode", debounced],
    queryFn: () => geocodeSearch(debounced),
    enabled: debounced.length >= 3,
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
}
