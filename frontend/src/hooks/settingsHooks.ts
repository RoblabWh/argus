import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { getSettings, updateWebodmSettings, updateDrzSettings, updateWeatherSettings, updateDetectionColors } from "@/api";

export function useSettings() {
    return useQuery({
        queryKey: ["settings"],
        queryFn: getSettings,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}

export function useUpdateWebodmSettings() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (newSettings: { ENABLE_WEBODM: boolean; WEBODM_URL: string; WEBODM_USERNAME: string; WEBODM_PASSWORD: string }) =>
            updateWebodmSettings(newSettings),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["settings"] });
        },
    });
}

export function useUpdateWeatherSettings() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (newSettings: { OPEN_WEATHER_API_KEY: string }) =>
            updateWeatherSettings(newSettings),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["settings"] });
        },
    });
}

export function useUpdateDrzSettings() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (newSettings: { BACKEND_URL: string; AUTHOR_NAME: string }) =>
            updateDrzSettings(newSettings),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["settings"] });
        },
    });
}

export function useUpdateDetectionColors() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (newSettings: { DETECTION_COLORS: { [key: string]: string } }) =>
            updateDetectionColors(newSettings),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["settings"] });
        },
    });
}