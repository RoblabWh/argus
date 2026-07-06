import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import {
    getSettings,
    updateWebodmSettings,
    updateDrzSettings,
    updateWeatherSettings,
    updateHuggingFaceSettings,
    updateDetectionColors,
    testWebodmSettings,
    testWeatherSettings,
    testDrzSettings,
    testHuggingFaceSettings,
} from "@/api";
import type {
    WebODMSettings,
    OpenWeatherSettings,
    HuggingFaceSettings,
    DRZSettings,
} from "@/types/settings";

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
        mutationFn: (newSettings: WebODMSettings) => updateWebodmSettings(newSettings),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["settings"] });
        },
    });
}

export function useUpdateWeatherSettings() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (newSettings: OpenWeatherSettings) => updateWeatherSettings(newSettings),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["settings"] });
        },
    });
}

export function useUpdateDrzSettings() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (newSettings: DRZSettings) => updateDrzSettings(newSettings),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["settings"] });
        },
    });
}

export function useUpdateHuggingFaceSettings() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (newSettings: HuggingFaceSettings) => updateHuggingFaceSettings(newSettings),
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

export function useTestWebodmSettings() {
    return useMutation({
        mutationFn: (s: WebODMSettings) => testWebodmSettings(s),
    });
}

export function useTestWeatherSettings() {
    return useMutation({
        mutationFn: (s: OpenWeatherSettings) => testWeatherSettings(s),
    });
}

export function useTestDrzSettings() {
    return useMutation({
        mutationFn: (s: DRZSettings) => testDrzSettings(s),
    });
}

export function useTestHuggingFaceSettings() {
    return useMutation({
        mutationFn: (s: HuggingFaceSettings) => testHuggingFaceSettings(s),
    });
}
