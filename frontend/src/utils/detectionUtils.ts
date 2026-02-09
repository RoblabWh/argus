/**
 * Detection filtering and threshold utilities
 * Pure functions for managing detection visibility and counting
 */

import type { Detection } from "@/types/detection";

/**
 * Count detections per class that meet the threshold requirements
 */
export function countDetections(
    detections: Detection[] | undefined,
    thresholds: Record<string, number> = {}
): Record<string, number> {
    console.log("Counting detections with thresholds:", thresholds);
    const summary: Record<string, number> = {};

    if (!detections || detections.length === 0 || Object.keys(thresholds).length === 0) {
        return summary;
    }

    detections.forEach((detection) => {
        if (!summary[detection.class_name]) {
            summary[detection.class_name] = 0;
        }
        if (detection.score < thresholds[detection.class_name]) {
            return; // Skip detections below threshold
        }
        summary[detection.class_name] += 1;
    });

    return summary;
}

/**
 * Create initial threshold map from detections with default value of 0.2
 */
export function initiateThresholds(
    detections: Detection[] | undefined
): Record<string, number> {
    if (!detections) return {};

    const thresholds: Record<string, number> = {};

    detections.forEach((detection) => {
        if (!(detection.class_name in thresholds)) {
            thresholds[detection.class_name] = 0.2; // Default threshold
        }
    });

    return thresholds;
}

/**
 * Create initial visibility map from detections with all categories visible
 */
export function initiateCategoryVisibility(
    detections: Detection[] | undefined
): Record<string, boolean> {
    const visibility: Record<string, boolean> = {};

    if (!detections) return visibility;

    detections.forEach((detection) => {
        if (!(detection.class_name in visibility)) {
            visibility[detection.class_name] = true; // Default to visible
        }
    });

    return visibility;
}

/**
 * Merge new detection classes into existing thresholds, preserving current values
 */
export function updateThresholds(
    detections: Detection[] | undefined,
    currentThresholds: Record<string, number>
): Record<string, number> {
    console.log("Updating thresholds with current:", currentThresholds);

    if (!detections) return currentThresholds;

    const thresholds = { ...currentThresholds };

    detections.forEach((detection) => {
        if (!(detection.class_name in thresholds)) {
            thresholds[detection.class_name] = 0.2; // Default threshold
        }
    });

    console.log("Updated thresholds:", thresholds);
    return thresholds;
}

/**
 * Merge new detection classes into existing visibility map, preserving current values
 */
export function updateCategoryVisibility(
    detections: Detection[] | undefined,
    currentVisibility: Record<string, boolean>
): Record<string, boolean> {
    if (!detections) return currentVisibility;

    const visibility = { ...currentVisibility };

    detections.forEach((detection) => {
        if (!(detection.class_name in visibility)) {
            visibility[detection.class_name] = true; // Default to visible
        }
    });

    return visibility;
}
