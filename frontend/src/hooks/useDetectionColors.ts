import { useEffect, useSyncExternalStore } from "react";
import {
    getDetectionColorsVersion,
    setDetectionColors,
    subscribeDetectionColors,
} from "@/types/detection";
import { useSettings } from "@/hooks/settingsHooks";

/**
 * Subscribe to the detection color store.
 *
 * Returns a version number that changes whenever the configured colors change.
 * Components call this so they re-render on a color change; memoized consumers
 * (e.g. MapTab's Leaflet icon caches) also put the value in their dependency
 * arrays so cached artifacts are rebuilt.
 */
export function useDetectionColorsVersion(): number {
    return useSyncExternalStore(subscribeDetectionColors, getDetectionColorsVersion);
}

/**
 * Mirror the server-side detection colors into the module-level store.
 *
 * Mount exactly once, high enough that every route benefits (App) — the colors
 * must be available without the user ever opening the settings page.
 */
export function useSyncDetectionColors(): void {
    const { data } = useSettings();
    const colors = data?.DETECTION_COLORS;
    useEffect(() => {
        setDetectionColors(colors);
    }, [colors]);
}
