/**
 * Coordinate and GPS utilities
 * Functions for UTM distance calculations, flight trajectory extraction, and detection GPS computation
 */

import type { ImageBasic, UTMCoord, GPSCoord } from "@/types/image";
import type { Detection } from "@/types/detection";
import type { Map } from "@/types/map";

/**
 * Calculate Euclidean distance between two UTM coordinates
 */
export function utmDistance(a: UTMCoord, b: UTMCoord): number {
    const dx = a.easting - b.easting;
    const dy = a.northing - b.northing;
    return Math.sqrt(dx * dx + dy * dy);
}

/**
 * Extract flight trajectory from images as GPS coordinates
 * Filters out thermal duplicates (when thermal and regular images are taken at same location)
 * Returns chronologically sorted [lat, lon] pairs
 */
export function extractFlightTrajectory(images: ImageBasic[]): [number, number][] {
    // Create a copy to avoid mutating the original array
    const sortedImages = [...images].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );

    const selected: ImageBasic[] = [];

    for (let i = 0; i < sortedImages.length; i++) {
        const img = sortedImages[i];
        if (!img.coord?.gps || img.panoramic) continue;

        const prev = selected[selected.length - 1];

        if (
            prev &&
            Math.abs(
                new Date(img.created_at).getTime() - new Date(prev.created_at).getTime()
            ) <= 2000 // within 2 seconds
        ) {
            // One thermal, one regular?
            if (img.thermal !== prev.thermal) {
                const utm1 = img.coord?.utm;
                const utm2 = prev.coord?.utm;

                if (utm1 && utm2) {
                    const dist = utmDistance(utm1, utm2);

                    if (dist <= 3.5) {
                        // keep the regular one
                        if (!img.thermal) {
                            selected[selected.length - 1] = img; // replace with regular
                        }
                        continue; // skip thermal
                    }
                }
            }
        }

        selected.push(img);
    }

    // Collect flight path coords
    return selected
        .filter((img) => img.coord?.gps)
        .map((img) => [img.coord!.gps.lat, img.coord!.gps.lon]);
}

/**
 * Compute GPS coordinates for a detection based on its bounding box position
 * within the image and the image's corner coordinates from the map
 */
export function computeDetectionGps(
    detection: Detection,
    images: ImageBasic[] | undefined,
    maps: Map[] | undefined
): GPSCoord | null {
    if (!images || !maps) return null;

    const image = images.find((img) => img.id === detection.image_id);
    if (!image || !image.coord) return null;

    const mapElement = maps
        .flatMap((m) => m.map_elements)
        .find((el) => el.image_id === image.id);
    if (!mapElement) return null;

    const cornersGps = mapElement.corners.gps;
    const boundsPx = detection.bbox;
    const imgWidth = image.width;
    const imgHeight = image.height;

    // Calculate relative position within image (center of bounding box)
    const relX = (Number(boundsPx[0]) + Number(boundsPx[2]) / 2) / imgWidth;
    const relY = (Number(boundsPx[1]) + Number(boundsPx[3]) / 2) / imgHeight;

    // Interpolate GPS position within map element corners
    // c0 = top-right, c1 = bottom-right, c2 = bottom-left, c3 = top-left
    const c0 = cornersGps[0];
    const c2 = cornersGps[2];
    const c3 = cornersGps[3];

    const lat = c3[0] + relX * (c0[0] - c3[0]) + relY * (c2[0] - c3[0]);
    const lon = c3[1] + relX * (c0[1] - c3[1]) + relY * (c2[1] - c3[1]);

    return { lat, lon };
}
