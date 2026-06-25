/**
 * Detection filtering and threshold utilities
 * Pure functions for managing detection visibility and counting
 */

import type { Detection, DetectionDisplayMode } from "@/types/detection";
import type { GPSCoord, ImageBasic } from "@/types/image";
import type { Map as MapData } from "@/types/map";
import { computeDetectionGps, isPointInPolygon } from "@/utils/coordinateUtils";

/** A detection with a resolved GPS position (from stored coord or bilinear interpolation). */
export type DetectionWithGps = Detection & { computedGps: GPSCoord };

/** A re-identification cluster rendered as a single merged map marker. */
export interface ClusterMarker {
    uid: number;
    members: DetectionWithGps[];
    /** Position of the merged marker (Voronoi-survivor member or the average — see reduceDetections). */
    centroid: GPSCoord;
    /** Always the plain average of member positions; used for the cluster outline circle. */
    averageCentroid: GPSCoord;
    className: string;
}

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
 * Group detections by their re-identification cluster label (unique_object_id).
 *
 * Detections sharing the same non-null `unique_object_id` are duplicate views of one
 * physical object across overlapping images. Returns the clusters keyed by id, plus the
 * leftover unassigned detections (unique_object_id null/undefined).
 */
export function groupDetectionsByObject<T extends Detection>(
    detections: T[] | undefined
): { clusters: Map<number, T[]>; unassigned: T[] } {
    const clusters = new Map<number, T[]>();
    const unassigned: T[] = [];

    for (const det of detections ?? []) {
        const uid = det.unique_object_id;
        if (uid === null || uid === undefined) {
            unassigned.push(det);
            continue;
        }
        const arr = clusters.get(uid);
        if (arr) arr.push(det);
        else clusters.set(uid, [det]);
    }

    return { clusters, unassigned };
}

/**
 * Compute the next free re-identification object id for manual assignment.
 * Ids are arbitrary ints chosen by the client (the backend applies them without checks).
 */
export function getNextObjectId(detections: Detection[] | undefined): number {
    let max = 0;
    for (const det of detections ?? []) {
        const uid = det.unique_object_id;
        if (typeof uid === "number" && uid > max) max = uid;
    }
    return max + 1;
}

/**
 * Build a lookup from image_id → Voronoi polygon (GPS coords) from the report's maps.
 */
export function buildVoronoiIndex(
    maps: MapData[] | undefined
): Map<number, [number, number][]> {
    const index = new Map<number, [number, number][]>();
    maps?.forEach((m) =>
        m.map_elements?.forEach((el) => {
            if (el.voronoi_gps?.length) index.set(el.image_id, el.voronoi_gps);
        })
    );
    return index;
}

/**
 * Reduce detections for display on the map and counting in the DetectionCard.
 *
 * Filtering by confidence threshold happens *before* grouping, so a cluster whose every member
 * falls below threshold simply ceases to exist. Visibility (per-class eye toggle) is NOT applied
 * here — it stays a pure display filter applied at render time, keeping counts visibility-independent.
 *
 * - "all": every threshold-passing detection is returned individually (no merge, no clip).
 * - "reduced": detections sharing a `unique_object_id` are merged into one cluster marker; the
 *   ungrouped leftovers are Voronoi-clipped to their owning image cell (graceful fallback: kept
 *   when no Voronoi cell is available).
 */
export function reduceDetections(
    detections: Detection[] | undefined,
    images: ImageBasic[] | undefined,
    maps: MapData[] | undefined,
    thresholds: Record<string, number>,
    mode: DetectionDisplayMode,
    clusterRepFromVoronoi = false
): { clusters: ClusterMarker[]; unassignedVisible: DetectionWithGps[] } {
    if (!detections?.length || !images?.length || !maps?.length) {
        return { clusters: [], unassignedVisible: [] };
    }

    const withGps = detections
        .filter((det) => det.score >= (thresholds[det.class_name] || 0))
        .map((det) => {
            const gps = det.coord?.gps || computeDetectionGps(det, images, maps);
            return gps ? ({ ...det, computedGps: gps } as DetectionWithGps) : null;
        })
        .filter(Boolean) as DetectionWithGps[];

    // "all" → every detection individually, no grouping, no clipping.
    if (mode === "all") {
        return { clusters: [], unassignedVisible: withGps };
    }

    const { clusters: rawClusters, unassigned } = groupDetectionsByObject(withGps);

    const voronoiIndex = buildVoronoiIndex(maps);

    // One merged marker per cluster. Default: positioned at the average of its members. When
    // clusterRepFromVoronoi is on, prefer a real member that survives Voronoi clipping (lands on
    // top of the object in the mosaic): the lone survivor, or — with several — the one closest to
    // the average center; clusters with no survivor fall back to the average.
    const clusters: ClusterMarker[] = Array.from(rawClusters.entries()).map(([uid, members]) => {
        const avgLat = members.reduce((s, m) => s + m.computedGps.lat, 0) / members.length;
        const avgLon = members.reduce((s, m) => s + m.computedGps.lon, 0) / members.length;
        let centroid: GPSCoord = { lat: avgLat, lon: avgLon };

        if (clusterRepFromVoronoi) {
            const survivors = members.filter((m) => {
                const voronoi = voronoiIndex.get(m.image_id);
                return voronoi
                    ? isPointInPolygon([m.computedGps.lat, m.computedGps.lon], voronoi)
                    : false;
            });
            if (survivors.length === 1) {
                centroid = survivors[0].computedGps;
            } else if (survivors.length > 1) {
                let best = survivors[0];
                let bestDist = Infinity;
                for (const s of survivors) {
                    const dist =
                        (s.computedGps.lat - avgLat) ** 2 + (s.computedGps.lon - avgLon) ** 2;
                    if (dist < bestDist) {
                        bestDist = dist;
                        best = s;
                    }
                }
                centroid = best.computedGps;
            }
        }

        return {
            uid,
            members,
            centroid,
            averageCentroid: { lat: avgLat, lon: avgLon },
            className: members[0].class_name,
        };
    });

    // Ungrouped detections keep the per-image Voronoi clip behavior.
    const unassignedVisible = unassigned.filter((det) => {
        const voronoi = voronoiIndex.get(det.image_id);
        if (!voronoi) return true; // no Voronoi data → always show
        return isPointInPolygon([det.computedGps.lat, det.computedGps.lon], voronoi);
    });

    return { clusters, unassignedVisible };
}

/** One currently-rendered map marker (a re-id cluster or an ungrouped detection). */
export interface SpatialMarkable {
    className: string;
    position: GPSCoord;
    ref:
        | { kind: "cluster"; cluster: ClusterMarker }
        | { kind: "detection"; detection: DetectionWithGps };
}

/** A proximity aggregation of same-class markables, shown as one numbered dot when zoomed out. */
export interface SpatialCluster {
    id: string; // grid key — stable React key
    center: GPSCoord; // unprojected average of member pixel positions
    className: string;
    count: number;
    members: SpatialMarkable[];
}

/**
 * Group markables that fall in the same pixel-grid cell (per class) into spatial clusters.
 *
 * Markers are projected to pixel space at a fixed zoom (pan-independent, so this only needs
 * recomputing when the zoom changes) and binned into a `cellSizePx` grid. The class name is part
 * of the bin key, so only same-class markers merge. Cells with a single markable are returned as
 * `singles` (render unchanged); cells with two or more become a `SpatialCluster` centered on the
 * unprojected average of its members' pixel positions.
 */
export function gridClusterMarkables(
    markables: SpatialMarkable[],
    project: (lat: number, lon: number) => { x: number; y: number },
    unproject: (x: number, y: number) => GPSCoord,
    cellSizePx = 100
): { clusters: SpatialCluster[]; singles: SpatialMarkable[] } {
    const bins = new Map<string, { members: SpatialMarkable[]; sumX: number; sumY: number }>();

    for (const m of markables) {
        const p = project(m.position.lat, m.position.lon);
        const col = Math.floor(p.x / cellSizePx);
        const row = Math.floor(p.y / cellSizePx);
        const key = `${col},${row},${m.className}`;
        const bin = bins.get(key);
        if (bin) {
            bin.members.push(m);
            bin.sumX += p.x;
            bin.sumY += p.y;
        } else {
            bins.set(key, { members: [m], sumX: p.x, sumY: p.y });
        }
    }

    const clusters: SpatialCluster[] = [];
    const singles: SpatialMarkable[] = [];

    for (const [key, bin] of bins) {
        if (bin.members.length === 1) {
            singles.push(bin.members[0]);
            continue;
        }
        clusters.push({
            id: key,
            center: unproject(bin.sumX / bin.members.length, bin.sumY / bin.members.length),
            className: bin.members[0].className,
            count: bin.members.length,
            members: bin.members,
        });
    }

    return { clusters, singles };
}

/**
 * Per-class count of a reduced set: each cluster counts as one object, each ungrouped (clipped)
 * detection counts as one.
 */
export function countReduced(
    reduced: { clusters: ClusterMarker[]; unassignedVisible: DetectionWithGps[] }
): Record<string, number> {
    const summary: Record<string, number> = {};
    for (const cluster of reduced.clusters) {
        summary[cluster.className] = (summary[cluster.className] || 0) + 1;
    }
    for (const det of reduced.unassignedVisible) {
        summary[det.class_name] = (summary[det.class_name] || 0) + 1;
    }
    return summary;
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
