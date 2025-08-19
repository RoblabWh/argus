import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ProcessingSettings } from "@/types/processing";

export function useReportSettings(
  reportId: number,
  dynamicDefaults: Partial<ProcessingSettings>
) {
  const queryClient = useQueryClient();

  const initialDefaults: ProcessingSettings = {
    keep_weather: false,
    fast_mapping: true,
    target_map_resolution: 6144,
    accepted_gimbal_tilt_deviation: 7.5,
    default_flight_height: 100.0,
    odm_processing: false,
    odm_full: false,
    ...dynamicDefaults,
  };

  // Subscribe to settings in the cache
  const { data: settings = initialDefaults } = useQuery({
    queryKey: ["report-settings", reportId],
    queryFn: async () => initialDefaults, // never actually fetch → just seed defaults
    initialData: () =>
      queryClient.getQueryData<ProcessingSettings>(["report-settings", reportId]) ??
      initialDefaults,
  });

  const setSettings = (newSettings: ProcessingSettings) => {
    queryClient.setQueryData(["report-settings", reportId], newSettings);
  };

  return { settings, setSettings };
}
