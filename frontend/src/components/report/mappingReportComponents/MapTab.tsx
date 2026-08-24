import React from "react";
import { useState, useEffect, useMemo, useRef } from "react";
import type { ImageBasic } from "@/types/image";
import type { Detection, FireMapRegion } from "@/types/detection";
import { getDetectionColor, confidenceToColor, CONFIDENCE_RAMP_GRADIENT, FIRE_CLASSES } from "@/types/detection";
import { useDetectionColorsVersion } from "@/hooks/useDetectionColors";
import { getApiUrl } from "@/api";
import {
    MapContainer,
    TileLayer,
    LayersControl,
    ImageOverlay,
    GeoJSON,
    Marker,
    Popup,
    Polygon,
    Polyline,
    Circle,
    LayerGroup,
    useMap
} from 'react-leaflet';
import { useTheme } from "@/components/ui/theme-provider";
import type { LatLngBoundsExpression, Map as LeafletMap } from 'leaflet';
import L from "leaflet";
import 'leaflet/dist/leaflet.css';
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Home, Group, Ungroup, CircleHelp, Contrast } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import "@/lib/Leaflet.ImageOverlay.Rotated";
import { RotatedImageOverlay } from "@/components/report/mappingReportComponents/RotatedImageOverlay";
import panoPinSVG from '@/assets/panorama.svg';
import { useImages } from "@/hooks/imageHooks";
import { useMaps } from "@/hooks/useMaps";
import { useDetections, useFireMap, useUpdateDetectionBatch } from "@/hooks/detectionHooks";
import { useThermalMap } from "@/hooks/useThermalMap";
import { temperatureToRampColor, TEMPERATURE_RAMP_GRADIENT } from "@/utils/thermalUtils";
import type { ThermalMapRegion } from "@/types/thermalData";
import type { TempFilters } from "@/components/report/mappingReportComponents/GalleryCardFiltered";
import { extractFlightTrajectory, computeDetectionGps, polygonIntersection } from "@/utils/coordinateUtils";
import { reduceDetections, gridClusterMarkables } from "@/utils/detectionUtils";
import type { DetectionWithGps, ClusterMarker, SpatialMarkable } from "@/utils/detectionUtils";
import type { DetectionDisplayMode } from "@/types/detection";
import { AssignObjectDialog } from "@/components/report/mappingReportComponents/AssignObjectDialog";

// Re-export for backward compatibility if other components import from here
export { extractFlightTrajectory } from "@/utils/coordinateUtils";

const { BaseLayer } = LayersControl;

// Cluster count badges are hidden below this zoom (too cluttered when zoomed out)
const CLUSTER_BADGE_MIN_ZOOM = 21;

// At or below this zoom, nearby same-class markers collapse into spatial super-cluster dots.
const SPATIAL_CLUSTER_MAX_ZOOM = 17;

// Experiment: derive a cluster's map marker from its Voronoi-clipped member instead of the average.
const CLUSTER_REP_FROM_VORONOI = true;

// Accent for image-footprint overlay polygons (reads on light + dark basemaps)
const FOOTPRINT_COLOR = "#0ea5e9"; // sky-500

/** Background-agnostic marker casing for high-contrast mode: a dark ring hugging the fill,
 *  a light ring outside it, so the marker reads on bright roofs and dark asphalt alike.
 *  box-shadow spreads don't affect layout, so every iconSize/iconAnchor stays valid and the
 *  ring can't shift a marker off its GPS point. */
function markerCasing(highContrast: boolean, normalShadow: string): string {
    return highContrast
        ? "0 0 0 3px #fff, 0 1px 2px rgba(0,0,0,0.55)"
        : normalShadow;
}

/** Radius in meters that encloses a cluster's members around its average center (with padding). */
function clusterRadiusMeters(cluster: ClusterMarker): number {
    const { lat, lon } = cluster.averageCentroid;
    const cosLat = Math.cos((lat * Math.PI) / 180);
    let rMax = 0;
    for (const m of cluster.members) {
        const dy = (m.computedGps.lat - lat) * 111320;
        const dx = (m.computedGps.lon - lon) * 111320 * cosLat;
        rMax = Math.max(rMax, Math.hypot(dx, dy));
    }
    return Math.max(rMax + 2, 5);
}

interface Props {
    reportId: number;
    selectImageOnMap: (image_id: number) => void;
    thresholds: { [key: string]: number };
    visibleCategories: { [key: string]: boolean };
    visibleMapOverlays: { [mapId: number]: boolean };
    setVisibleMapOverlays: (overlays: { [mapId: number]: boolean }) => void;
    detectionMode: DetectionDisplayMode;
    setDetectionMode: (v: DetectionDisplayMode) => void;
    selectedObjectId: number | null;
    setSelectedObjectId: (id: number | null) => void;
    highlightedDetectionId: number | null;
    setHighlightedDetectionId: (id: number | null) => void;
    setRegionImageIds: (ids: number[] | null) => void;
    tempFilter: TempFilters;
}

function MapTabComponent({ reportId, selectImageOnMap, thresholds, visibleCategories, visibleMapOverlays, setVisibleMapOverlays, detectionMode, selectedObjectId, setSelectedObjectId, setHighlightedDetectionId, setRegionImageIds, tempFilter }: Props) {
    const [overlayOpacity, setOverlayOpacity] = useState(1.0);
    const [map, setMap] = useState<LeafletMap | null>(null);
    const { data: images } = useImages(reportId);
    const { data: maps } = useMaps(reportId);
    const { data: detections } = useDetections(reportId);
    const { mutate: updateDetections } = useUpdateDetectionBatch(reportId);
    const api_url = getApiUrl();
    const { theme } = useTheme();
    const [showTrajectory, setShowTrajectory] = useState(true);
    const [showPanoMarkers, setShowPanoMarkers] = useState(true);
    const [showDetections, setShowDetections] = useState(true);
    const [showPolygons, setShowPolygons] = useState(true);
    const [showFireMap, setShowFireMap] = useState(true);
    // Server-generated fire overlay (confidence bands + region->image table),
    // recomputed when the fire-class detection threshold changes.
    const fireMapQuery = useFireMap(reportId, showFireMap, thresholds["fire"]);
    const fireMap = fireMapQuery.data;
    const hasFireOverlay = !!fireMap?.geojson?.features?.length;
    // Server-generated temperature overlay (10 °C bands, clipped to the
    // gallery's temp filters). Off by default — the first request builds the
    // per-map composite cache.
    const [showTempMap, setShowTempMap] = useState(false);
    const thermalMapQuery = useThermalMap(reportId, tempFilter, showTempMap);
    const thermalMap = thermalMapQuery.data;
    const hasThermalOverlay = !!thermalMap?.geojson?.features?.length;
    // Displayed (filter-clipped) temperature range — the color ramp is re-fit
    // to it so high-filtered views don't collapse into the white ramp tip.
    const thermalDisplayRange = useMemo(() => {
        const range = thermalMap?.range;
        if (!range) return null;
        const lo = Math.max(tempFilter.minAtLeast ?? -Infinity, range.min);
        const hi = Math.min(tempFilter.maxAtMost ?? Infinity, range.max);
        return lo <= hi ? { lo, hi } : { lo: range.min, hi: range.max };
    }, [thermalMap?.range, tempFilter.minAtLeast, tempFilter.maxAtMost]);
    const [spatialClusterEnabled, setSpatialClusterEnabled] = useState(true);
    // Opt-in high-contrast marker style (opaque fill + black/white double halo) for
    // backgrounds the class colors wash out against.
    const [highContrast, setHighContrast] = useState(false);
    // Bumped when the configured detection colors change; the icon caches below
    // key on it so a color edit in the settings page repaints the markers.
    const colorsVersion = useDetectionColorsVersion();
    const [editDetection, setEditDetection] = useState<Detection | null>(null);
    const [zoom, setZoom] = useState(18);
    const current = theme === "system"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light"
        : theme;

    const first_image_with_gps = images?.find((image) => image.coord);
    const first_map = maps?.[0] || null;
    const [center, setCenter] = useState(first_map
        ? [(first_map.bounds.gps.latitude_min + first_map.bounds.gps.latitude_max) / 2, (first_map.bounds.gps.longitude_min + first_map.bounds.gps.longitude_max) / 2]
        : (first_image_with_gps ? [first_image_with_gps.coord.gps.lat, first_image_with_gps.coord.gps.lon] : [51.574, 7.027]));


    const bounds = useMemo(() => {
        if (!maps?.length) return null;

        const gps = maps[0].bounds.gps;
        return [
            [gps.latitude_min, gps.longitude_min],
            [gps.latitude_max, gps.longitude_max]
        ] as LatLngBoundsExpression;
    }, [maps]);

    // Memoize flight trajectory - only recalculate when images change
    const flightTrajectory = useMemo(() => {
        if (!images?.length) return [];
        return extractFlightTrajectory([...images]);
    }, [images]);

    // Cache detection icons by class name (+ highlighted variant for selected cluster children)
    const detectionIconCache = useMemo(() => {
        const cache = new Map<string, L.DivIcon>();
        const getIcon = (className: string, highlighted = false) => {
            const key = `${className}|${highlighted ? 1 : 0}`;
            if (!cache.has(key)) {
                const color = getDetectionColor(className, false);
                const centerColor = getDetectionColor(className, true);
                // High contrast: opaque fill, no same-color border (the black casing ring
                // replaces it), +2px so the core still reads inside the two rings.
                const size = highlighted ? (highContrast ? 15 : 14) : (highContrast ? 13 : 11);
                const fill = highContrast ? color : centerColor;
                const border = highContrast ? "3px solid black" : `2px solid ${color}`;
                const shadow = highlighted
                    ? `0 1px 8px rgba(0,0,0,0.65)`
                    : `0 2px 5px rgba(0,0,0,0.45)`;
                cache.set(key, L.divIcon({
                    className: 'custom-div-icon',
                    html: `<div class="marker-dot" style="background-color:${fill};width:${size}px;height:${size}px;border-radius:50%;border:${border};box-shadow:${markerCasing(highContrast, shadow)};box-sizing:border-box;"></div>`,
                    //html: `<div style="background-color:${color};opacity:0.85;width:14px;height:14px;border-radius:50%;border:2px solid black;"></div>`,
                    iconSize: [size, size],
                    iconAnchor: [size / 2, size / 2],
                    popupAnchor: [0, -size / 2],
                }));
            }
            return cache.get(key)!;
        };
        return getIcon;
        // Toggling contrast, or editing the class colors, discards the cache so every
        // marker gets a fresh icon — a few dozen tiny DivIcons, rebuilt only on an
        // explicit user action.
    }, [highContrast, colorsVersion]);

    // Cache merged-cluster icons by class + count + whether the count badge is shown (zoom-gated)
    const getClusterIcon = useMemo(() => {
        const cache = new Map<string, L.DivIcon>();
        return (className: string, count: number, showBadge: boolean) => {
            const key = `${className}|${count}|${showBadge ? 1 : 0}`;
            if (!cache.has(key)) {
                const color = getDetectionColor(className, false);
                const centerColor = getDetectionColor(className, true);
                const badge = showBadge
                    ? `<span style="position:absolute;top:-7px;right:-7px;background:#111;color:#fff;border-radius:9px;font-size:10px;line-height:14px;min-width:14px;height:14px;text-align:center;padding:0 2px;border:1px solid #fff;box-sizing:border-box;">${count}</span>`
                    : "";
                // The +2px and the casing rings both fit inside the existing 22px icon box,
                // so the wrapper and badge offsets stay untouched. The dot sits at the
                // wrapper's top-left rather than centered, so the +2px is pulled back by 1px
                // to keep its center — and thus the marker's screen position — unchanged.
                const dot = highContrast ? 13 : 11;
                const dotOffset = highContrast ? "margin:-1px 0 0 -1px;" : "";
                const fill = highContrast ? color : centerColor;
                const border = highContrast ? "3px solid black" : `2px solid ${color}`;
                cache.set(key, L.divIcon({
                    className: 'custom-div-icon',
                    html: `<div style="position:relative;width:16px;height:16px;">
                        <div class="marker-dot" style="background-color:${fill};width:${dot}px;height:${dot}px;border-radius:50%;border:${border};box-shadow:${markerCasing(highContrast, "0 1px 4px rgba(0,0,0,0.5)")};box-sizing:border-box;${dotOffset}"></div>
                        ${badge}
                    </div>`,
                    iconSize: [22, 22],
                    iconAnchor: [11, 11],
                    popupAnchor: [0, -11],
                }));
            }
            return cache.get(key)!;
        };
    }, [highContrast, colorsVersion]);

    // Cache spatial super-cluster icons (zoomed-out proximity aggregation) by class + count.
    // Visually distinct from re-id markers: a larger filled dot with the count *inside*.
    const getSpatialClusterIcon = useMemo(() => {
        const cache = new Map<string, L.DivIcon>();
        return (className: string, count: number) => {
            const key = `${className}|${count}`;
            if (!cache.has(key)) {
                const centerColor = getDetectionColor(className, true);
                const color = getDetectionColor(className, false);
                const size = 24;
                // This icon already has two concentric elements, so the double halo reuses
                // their borders (black inner / white outer) instead of a box-shadow casing —
                // a 3px white spread would collide with the 2px gap to the outer ring.
                const outerBorder = highContrast ? "#fff" : centerColor;
                const innerBorder = highContrast ? "#000" : color;
                const dotShadow = highContrast ? "0 1px 2px rgba(0,0,0,0.55)" : "0 2px 6px rgba(0,0,0,0.5)";
                // The #111 digit is illegible on dark class colors — outline it in white.
                const countOutline = highContrast
                    ? "text-shadow:0 1px 0 #fff,1px 0 0 #fff,0 -1px 0 #fff,-1px 0 0 #fff;"
                    : "";
                cache.set(key, L.divIcon({
                    className: 'custom-div-icon',
                    html: `<div class="spatial-cluster spatial-cluster-ring" style="--ring-active:${color};width:${size+8}px;height:${size+8}px;border-radius:50%;border:2px solid ${outerBorder};box-sizing:border-box;display:flex;align-items:center;justify-content:center;">
                            <div style="background-color:${color};width:${size}px;height:${size}px;border-radius:50%;border:2px solid ${innerBorder};box-shadow:${dotShadow};box-sizing:border-box;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;line-height:1;color:#000000;${countOutline}">${count}</div>
                            </div>`,
                    iconSize: [size + 8, size + 8],
                    iconAnchor: [size / 2 + 4, size / 2 + 4],
                    popupAnchor: [0, -size / 2 - 4],
                }));
            }
            return cache.get(key)!;
        };
    }, [highContrast, colorsVersion]);

    // Fire-class detections never render as individual map markers — they are
    // shown as the fire overlay instead (the slideshow keeps their bboxes).
    const markerDetections = useMemo(
        () => detections?.filter(d => !FIRE_CLASSES.has(d.class_name)),
        [detections]
    );

    // Threshold-filtered detections with GPS, reduced per the display mode (shared with the
    // DetectionCard count so the map and the table stay consistent). Visibility (per-class eye
    // toggle) is applied as a render-time filter below, not here.
    const reduced = useMemo(
        () => reduceDetections(markerDetections, images, maps, thresholds, detectionMode, CLUSTER_REP_FROM_VORONOI),
        [markerDetections, images, maps, thresholds, detectionMode]
    );

    const clusters: ClusterMarker[] = useMemo(
        () => reduced.clusters.filter(c => visibleCategories[c.className]),
        [reduced, visibleCategories]
    );
    const unassignedVisible: DetectionWithGps[] = useMemo(
        () => reduced.unassignedVisible.filter(d => visibleCategories[d.class_name]),
        [reduced, visibleCategories]
    );

    const hasDetectionMarkers = clusters.length > 0 || unassignedVisible.length > 0;

    // Spotlight: when a cluster is selected, fade everything that isn't its children.
    // Tied to an actually-present cluster, so "all" mode (no clusters) or a hidden-class
    // selection never dims the map with nothing to highlight.
    const selectedCluster = selectedObjectId != null ? clusters.find(c => c.uid === selectedObjectId) : undefined;
    const spotlight = selectedCluster != null;

    // Spatial (proximity) clustering for zoomed-out views: aggregate nearby same-class markers
    // into numbered dots. Disabled above the zoom threshold and while a re-id cluster is expanded.
    const spatialView = useMemo(() => {
        if (!map || zoom > SPATIAL_CLUSTER_MAX_ZOOM || spotlight || !spatialClusterEnabled) {
            return { active: false as const };
        }
        const markables: SpatialMarkable[] = [
            ...clusters.map((c): SpatialMarkable => ({
                className: c.className,
                position: c.centroid,
                ref: { kind: "cluster", cluster: c },
            })),
            ...unassignedVisible.map((d): SpatialMarkable => ({
                className: d.class_name,
                position: d.computedGps,
                ref: { kind: "detection", detection: d },
            })),
        ];
        const project = (lat: number, lon: number) => map.project([lat, lon], zoom);
        const unproject = (x: number, y: number) => {
            const ll = map.unproject([x, y], zoom);
            return { lat: ll.lat, lon: ll.lng };
        };
        const { clusters: spatialClusters, singles } = gridClusterMarkables(markables, project, unproject);
        return { active: true as const, clusters: spatialClusters, singles };
    }, [map, zoom, spotlight, spatialClusterEnabled, clusters, unassignedVisible]);

    const getCenter = (corners: [number, number][]): [number, number] => {
        const lat = (corners[0][0] + corners[1][0] + corners[2][0] + corners[3][0]) / 4;    
        const lon = (corners[0][1] + corners[1][1] + corners[2][1] + corners[3][1]) / 4;
        return [lat, lon];
    }

    // Position the initial view from the first GPS-bearing image — but only once. Running on
    // every `images` change would snap the user's zoom/pan back to 18 on each refetch / new
    // detection batch during processing.
    useEffect(() => {
        if (didInitView.current) return;
        const first_image_with_gps = images?.find((image) => image.coord);
        if (first_image_with_gps && first_image_with_gps.coord?.gps) {
            setCenter([first_image_with_gps.coord.gps.lat, first_image_with_gps.coord.gps.lon]);
            map?.setView([first_image_with_gps.coord.gps.lat, first_image_with_gps.coord.gps.lon], 18);
            didInitView.current = true;
        }
    }, [images, map]);

    useEffect(() => {
        if (maps && setVisibleMapOverlays) {
            let newState: { [mapId: number]: boolean } = {};
            maps.forEach((map) => {
                if (visibleMapOverlays[map.id] === undefined) {
                    newState[map.id] = true;
                } else {
                    newState[map.id] = visibleMapOverlays[map.id];
                }
            });
            setVisibleMapOverlays(newState);
        }
    }, [maps]);

    const cornerRefs = useRef<Map<number, L.Polygon>>(new Map());

    // Detection ids we've already attempted a GPS backfill for. Prevents the
    // invalidate → refetch → re-select → PUT loop when a backfilled coord doesn't come back
    // populated, while still allowing *new* detection batches (new ids) to be backfilled
    // during processing. Reset when the report changes.
    const attemptedBackfillIds = useRef<Set<number>>(new Set());
    // Whether the map's initial view has been positioned from the first GPS-bearing image.
    const didInitView = useRef(false);
    useEffect(() => {
        attemptedBackfillIds.current = new Set();
        didInitView.current = false;
    }, [reportId]);

    const handleOverlayClick = (mapId: number, elementId: number, image_id: number) => {
        // While a cluster is active, a click on the background (which usually lands on an overlay
        // polygon) should only deselect it — not navigate to the image.
        if (selectedObjectId != null) {
            setSelectedObjectId(null);
            setHighlightedDetectionId(null);
            return;
        }
        selectImageOnMap(image_id);
    };

    // Whether the report has thermally analyzable images at all (drives the
    // Temp map toggle visibility; color-mapped-only thermal images don't count).
    const hasThermalCapable = useMemo(
        () => !!images?.some((img) => img.thermal && img.thermal_data?.min_temp != null),
        [images]
    );

    // Popup for a temperature-overlay region: band range + region max + the
    // same "Show source images" gallery-filter button as fire regions.
    const buildThermalRegionPopup = (bandMin: number, bandMax: number, region: ThermalMapRegion) => {
        const root = document.createElement("div");
        root.className = "w-44";
        const title = document.createElement("div");
        const imgLabel = `${region.images.length} image${region.images.length === 1 ? "" : "s"}`;
        title.innerHTML =
            `<strong>Temperature ${bandMin}–${bandMax} °C</strong><br/>` +
            `Region max: ${region.max_temp} °C<br/>` +
            `<span class="text-xs text-gray-500">covered by ${imgLabel}</span>`;
        root.appendChild(title);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "mt-2 w-full inline-flex items-center justify-center rounded-md text-sm font-medium h-8 px-3 bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer";
        button.textContent = "Show source images";
        button.addEventListener("click", () => {
            setSelectedObjectId(null);
            setHighlightedDetectionId(null);
            setRegionImageIds(region.images.map((img) => img.image_id));
            map?.closePopup();
        });
        root.appendChild(button);
        return root;
    };

    // Popup for a fire-overlay region: a short summary plus a button that
    // filters the gallery to the region's source images (thumbnails belong to
    // the gallery card, not a map popup — same idea as object groups).
    // Plain DOM because GeoJSON layers bind Leaflet popups, not React nodes.
    const buildFireRegionPopup = (region: FireMapRegion) => {
        const root = document.createElement("div");
        root.className = "w-44";
        const title = document.createElement("div");
        const detLabel = `${region.detection_count} detection${region.detection_count === 1 ? "" : "s"}`;
        const imgLabel = `${region.images.length} image${region.images.length === 1 ? "" : "s"}`;
        title.innerHTML =
            `<strong>Potential fire</strong><br/>` +
            `Max confidence: ${(region.max_score * 100).toFixed(1)}%<br/>` +
            `<span class="text-xs text-gray-500">${detLabel} from ${imgLabel}</span>`;
        root.appendChild(title);
        const button = document.createElement("button");
        button.type = "button";
        // Mirrors the shadcn Button used in the detection popups
        button.className = "mt-2 w-full inline-flex items-center justify-center rounded-md text-sm font-medium h-8 px-3 bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer";
        button.textContent = "Show source images";
        button.addEventListener("click", () => {
            // An open object group forces the gallery's objects view — clear it
            // so the image grid (which the filter applies to) becomes visible.
            setSelectedObjectId(null);
            setHighlightedDetectionId(null);
            setRegionImageIds(region.images.map((img) => img.image_id));
            map?.closePopup();
        });
        root.appendChild(button);
        return root;
    };

    const renderDetectionPopup = (detection: DetectionWithGps) => (
        <Popup>
            <div className="w-36">
                <strong>{detection.class_name}</strong><br />
                Confidence: {(detection.score * 100).toFixed(1)}%<br />
                Image ID: {detection.image_id}
                <span className="text-xs text-gray-500 my-0">ID {detection.id} /
                unique object ID {detection.unique_object_id ?? "unset"}</span>
                <Button onClick={() => {
                    selectImageOnMap(detection.image_id);
                }} className="text-sm w-full mt-2">Show</Button>
                <Button variant="outline" onClick={() => {
                    setEditDetection(detection);
                }} className="text-sm w-full mt-1">
                    {detection.unique_object_id == null ? "Set object ID" : "Change object ID"}
                </Button>
            </div>
        </Popup>
    );

    // An ungrouped detection as an individual marker (clicking clears any cluster selection).
    const renderUnassignedMarker = (detection: DetectionWithGps) => (
        <Marker
            key={`det-${detection.id}`}
            position={[detection.computedGps.lat, detection.computedGps.lon]}
            icon={detectionIconCache(detection.class_name)}
            opacity={spotlight ? 0.3 : 1}
            eventHandlers={{ click: () => { setSelectedObjectId(null); setHighlightedDetectionId(null); } }}
        >
            {renderDetectionPopup(detection)}
        </Marker>
    );

    // A re-id cluster as one merged marker; expands to highlighted child markers when selected.
    const renderClusterMarker = (cluster: ClusterMarker) => {
        if (cluster.uid === selectedObjectId) {
            return cluster.members.map(member => (
                <Marker
                    key={`obj-${cluster.uid}-det-${member.id}`}
                    position={[member.computedGps.lat, member.computedGps.lon]}
                    icon={detectionIconCache(member.class_name, true)}
                    eventHandlers={{ click: () => setHighlightedDetectionId(member.id) }}
                >
                    {renderDetectionPopup(member)}
                </Marker>
            ));
        }
        return (
            <Marker
                key={`obj-${cluster.uid}`}
                position={[cluster.centroid.lat, cluster.centroid.lon]}
                icon={getClusterIcon(cluster.className, cluster.members.length, !spotlight && zoom >= CLUSTER_BADGE_MIN_ZOOM)}
                opacity={spotlight ? 0.3 : 1}
                eventHandlers={{ click: () => setSelectedObjectId(cluster.uid) }}
            />
        );
    };

    useEffect(() => {
        if (!detections?.length || !images?.length || !maps?.length) return;

        // Find detections missing GPS that we haven't already tried to backfill. Skipping
        // already-attempted ids breaks the invalidate → refetch → re-select → PUT loop that
        // occurs when a backfilled coord doesn't come back populated, while still letting new
        // detection batches (new ids) arriving during processing get backfilled.
        const toUpdate = detections
            .filter(det => (!det.coord?.gps?.lat || !det.coord?.gps?.lon) && !attemptedBackfillIds.current.has(det.id))
            .map(det => {
                const gps = computeDetectionGps(det, images, maps);
                if (!gps) return null;
                det.coord = { gps: gps, utm: undefined };
                return det;
            })
            .filter(Boolean) as Detection[];

        // Send a single batch PUT if needed
        if (toUpdate.length > 0 && updateDetections) {
            toUpdate.forEach(det => attemptedBackfillIds.current.add(det.id));
            updateDetections(toUpdate);
        }
    }, [detections, images, maps, updateDetections]);

    useEffect(() => {
        if (map !== null) {
            // Resize observer to handle map container resizing
            const resizeObserver = new ResizeObserver(() => {
                if (!map) return;
                try {
                    map.invalidateSize();
                } catch (error) {
                    return;
                }
            });
            resizeObserver.observe(map.getContainer());
            return () => resizeObserver.disconnect();
        }
    }, [map]);

    useEffect(() => {
        if (!map) return;

        const handleOverlayAdd = (e: any) => {
            const overlayName = e.name ?? e.layer?.options?.name;
            if (!overlayName) return;

            setVisibleMapOverlays(prev => {
                const next = { ...prev };
                const found = maps?.find(m => `Map: ${m.name}` === overlayName);
                if (found) next[found.id] = true;
                return next;
            });
        };

        const handleOverlayRemove = (e: any) => {
            const overlayName = e.name ?? e.layer?.options?.name;
            if (!overlayName) return;

            setVisibleMapOverlays(prev => {
                const next = { ...prev };
                const found = maps?.find(m => `Map: ${m.name}` === overlayName);
                if (found) next[found.id] = false;
                return next;
            });
        };

        map.on("overlayadd", handleOverlayAdd);
        map.on("overlayremove", handleOverlayRemove);

        return () => {
            map.off("overlayadd", handleOverlayAdd);
            map.off("overlayremove", handleOverlayRemove);
        };
    }, [map, maps, setVisibleMapOverlays]);

    useEffect(() => {
        if (map !== null && bounds) {
            map.fitBounds(bounds);
        }
    }, [map, bounds]);

    // Clicking the empty map background clears the selected re-id cluster (collapses children).
    // Leaflet markers stop propagation, so this only fires on bare-map clicks.
    useEffect(() => {
        if (!map) return;
        const handler = () => { setSelectedObjectId(null); setHighlightedDetectionId(null); };
        map.on("click", handler);
        return () => { map.off("click", handler); };
    }, [map, setSelectedObjectId, setHighlightedDetectionId]);

    // Track zoom so cluster count badges can be hidden when zoomed out
    useEffect(() => {
        if (!map) return;
        setZoom(map.getZoom());
        const handler = () => setZoom(map.getZoom());
        map.on("zoomend", handler);
        return () => { map.off("zoomend", handler); };
    }, [map]);

    return (
        <div className="w-full h-full relative">
            <MapContainer center={center} zoom={18.5} ref={setMap} style={{ zIndex: 0, flex: 1, height: '100%', cursor: 'default' }}>
                <LayersControl position="topright">
                    <BaseLayer checked name="Mapbox Streets">
                        <TileLayer
                            id={current === "dark" ? 'mapbox/dark-v11' : 'mapbox/streets-v11'}
                            attribution='&copy; Mapbox contributors'
                            url="https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=pk.eyJ1Ijoicm9ibGFidXNlcndocyIsImEiOiJja3VjaXF3d2MxMTN5Mm9tdmQzaGphdGU3In0.BhKF_054bVOPcviIq2yIKg"
                            maxZoom={23}
                        />
                    </BaseLayer>

                    <BaseLayer name="OpenStreetMap">
                        <TileLayer
                            attribution='&copy; OpenStreetMap contributors'
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                            maxZoom={22}
                        />
                    </BaseLayer>

                    <BaseLayer name="Esri Satellite">
                        <TileLayer
                            attribution='Tiles © Esri'
                            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                            maxZoom={21}
                        />
                    </BaseLayer>

                    <BaseLayer name="Mapbox Satellite">
                        <TileLayer
                            id='mapbox/satellite-v9'
                            attribution='&copy; Mapbox contributors'
                            url="https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=pk.eyJ1Ijoicm9ibGFidXNlcndocyIsImEiOiJja3VjaXF3d2MxMTN5Mm9tdmQzaGphdGU3In0.BhKF_054bVOPcviIq2yIKg"
                            maxZoom={23}
                        />
                    </BaseLayer>

                    {flightTrajectory.length > 0 && showTrajectory && (
                        <LayerGroup>
                            <Polyline
                                positions={flightTrajectory}
                                pathOptions={{ color: 'magenta', weight: 2, opacity: spotlight ? 0.25 : 1 }}
                            />
                        </LayerGroup>
                    )}
                    {hasDetectionMarkers && showDetections && (
                        <LayerGroup>
                            {/* Faint outline grouping the selected cluster's members together */}
                            {selectedCluster && (
                                <Circle
                                    center={[selectedCluster.averageCentroid.lat, selectedCluster.averageCentroid.lon]}
                                    radius={clusterRadiusMeters(selectedCluster)}
                                    pathOptions={{
                                        color: getDetectionColor(selectedCluster.className),
                                        weight: 2,
                                        opacity: 0.7,
                                        fillOpacity: 0.08,
                                        dashArray: '4 5',
                                    }}
                                />
                            )}

                            {spatialView.active ? (
                                <>
                                    {/* Spatial super-clusters — numbered dots; click zooms in until members separate */}
                                    {spatialView.clusters.map(sc => (
                                        <Marker
                                            key={`spatial-${sc.id}`}
                                            position={[sc.center.lat, sc.center.lon]}
                                            icon={getSpatialClusterIcon(sc.className, sc.count)}
                                            eventHandlers={{
                                                click: () => {
                                                    if (!map) return;
                                                    const latlngs = sc.members.map(m => [m.position.lat, m.position.lon]) as [number, number][];
                                                    map.fitBounds(L.latLngBounds(latlngs), { padding: [40, 40], maxZoom: 19 });
                                                },
                                            }}
                                        />
                                    ))}
                                    {/* Lone markers in their cell render normally */}
                                    {spatialView.singles.map(m =>
                                        m.ref.kind === "detection"
                                            ? renderUnassignedMarker(m.ref.detection)
                                            : renderClusterMarker(m.ref.cluster)
                                    )}
                                </>
                            ) : (
                                <>
                                    {/* Unassigned detections — individual markers */}
                                    {unassignedVisible.map(renderUnassignedMarker)}
                                    {/* Re-id clusters — one merged marker per object; expands when selected */}
                                    {clusters.map(renderClusterMarker)}
                                </>
                            )}
                        </LayerGroup>
                    )}
                    {/* Fire overlay: smoothly merged fire detections as confidence
                        bands (purple = low, bright yellow = high). Painted low band
                        first, so higher-confidence cores sit on top (height-map look).
                        key remounts the layer when new data arrives — react-leaflet's
                        GeoJSON reads `data` only on mount. */}
                    {showFireMap && hasFireOverlay && fireMap?.geojson && (
                        <LayerGroup>
                            <GeoJSON
                                key={`fire-${fireMapQuery.dataUpdatedAt}`}
                                data={fireMap.geojson}
                                style={(feature) => ({
                                    stroke: false,
                                    fillColor: confidenceToColor(feature?.properties?.conf_min ?? 0),
                                    fillOpacity: 0.3,
                                })}
                                onEachFeature={(feature, layer) => {
                                    const region = fireMap.regions[String(feature.properties?.region_id)];
                                    if (region) {
                                        layer.bindPopup(buildFireRegionPopup(region), { minWidth: 200 });
                                    }
                                    layer.on({
                                        mouseover: () => (layer as L.Path).setStyle({ fillOpacity: 0.7 }),
                                        mouseout: () => (layer as L.Path).setStyle({ fillOpacity: 0.3 }),
                                    });
                                }}
                            />
                        </LayerGroup>
                    )}
                    {/* Temperature overlay: the report's thermal matrices merged
                        (max) and banded in 10 °C steps, clipped to the gallery's
                        temp filters. Colored on the ironbow ramp over the report's
                        full temperature range so colors stay stable while filtering. */}
                    {showTempMap && hasThermalOverlay && thermalMap?.geojson && (
                        <LayerGroup>
                            <GeoJSON
                                key={`thermal-${thermalMapQuery.dataUpdatedAt}`}
                                data={thermalMap.geojson}
                                style={(feature) => ({
                                    stroke: false,
                                    fillColor: temperatureToRampColor(
                                        feature?.properties?.temp_min ?? 0,
                                        thermalDisplayRange?.lo ?? 0,
                                        thermalDisplayRange?.hi ?? 100,
                                        tempFilter.minAtLeast,
                                    ),
                                    fillOpacity: 0.5,
                                })}
                                onEachFeature={(feature, layer) => {
                                    const region = thermalMap.regions[String(feature.properties?.region_id)];
                                    if (region) {
                                        layer.bindPopup(
                                            buildThermalRegionPopup(
                                                feature.properties?.temp_min,
                                                feature.properties?.temp_max,
                                                region,
                                            ),
                                            { minWidth: 200 },
                                        );
                                    }
                                    layer.on({
                                        mouseover: () => (layer as L.Path).setStyle({ fillOpacity: 0.7 }),
                                        mouseout: () => (layer as L.Path).setStyle({ fillOpacity: 0.5 }),
                                    });
                                }}
                            />
                        </LayerGroup>
                    )}
                    {(images && images.length > 0 && images.some(image => image.panoramic)) && showPanoMarkers && (
                        <LayerGroup>
                            {images.map((image) => {
                                if (!image.coord || !image.coord.gps || image.coord.gps === undefined || !image.panoramic) return null;
                                return (
                                    <Marker
                                        key={image.id}
                                        position={[image.coord.gps.lat, image.coord.gps.lon]}
                                        opacity={spotlight ? 0.3 : 1}
                                        eventHandlers={{
                                            click: () => {
                                                selectImageOnMap(image.id);
                                            },
                                        }}
                                        icon={L.icon({
                                            iconUrl: panoPinSVG,
                                            iconSize: [24, 24],
                                            iconAnchor: [12, 12],
                                            popupAnchor: [0, -12],
                                        })}
                                    >
                                    </Marker>
                                );
                            })}
                        </LayerGroup>
                    )}

                    {maps?.map((map) => {
                        const { latitude_min, latitude_max, longitude_min, longitude_max } = map.bounds.gps;
                        let useRotatedOverlay = false;
                        let gps_corners: LatLngBoundsExpression[] = [];

                        const bounds: LatLngBoundsExpression = [
                            [latitude_min, longitude_min],
                            [latitude_max, longitude_max],
                        ];

                        if (!map.bounds.corners || map.bounds.corners.gps.length < 4) {
                            console.warn(`Map ${map.name} does not have enough corners defined, using default bounds.`);
                            useRotatedOverlay = false;
                        } else {
                            useRotatedOverlay = true;
                            gps_corners = map.bounds.corners.gps.map((corner: LatLngBoundsExpression) => ([corner[1], corner[0]]));
                        }

                        return (
                            <LayersControl.Overlay
                                key={map.id}
                                name={`Map: ${map.name}`}
                                checked={visibleMapOverlays[map.id]}
                            >
                                <LayerGroup>
                                    {useRotatedOverlay ? (
                                        <RotatedImageOverlay
                                            url={`${api_url}/${map.url}`}
                                            corners={[
                                                gps_corners[0],
                                                gps_corners[1],
                                                gps_corners[3],
                                            ]}
                                            opacity={overlayOpacity}
                                        />) : (
                                        <ImageOverlay
                                            url={`${api_url}/${map.url}`}
                                            bounds={bounds}
                                            opacity={overlayOpacity}
                                        />
                                    )}

                                    {/* Pass 1: corner polygons (below) — registered via ref for cross-hover */}
                                    {showPolygons && map.map_elements?.map((element) => {
                                        const corners = element.corners.gps;
                                        const hasVoronoi = element.voronoi_gps && element.voronoi_gps.length > 0;
                                        
                                        return (
                                            <Polygon
                                                key={`map-${map.id}_corner-${element.id}`}
                                                ref={(layer) => {
                                                    if (layer) cornerRefs.current.set(element.id, layer);
                                                    else cornerRefs.current.delete(element.id);
                                                }}
                                                positions={[corners[0], corners[1], corners[2], corners[3]]}
                                                pathOptions={{
                                                    className: 'map-footprint',
                                                    fillColor: FOOTPRINT_COLOR,
                                                    color: FOOTPRINT_COLOR,
                                                    weight: 2,
                                                    // color: 'black',
                                                    // weight: 4,
                                                    opacity: 0,
                                                    fillOpacity: 0,
                                                    lineJoin: 'round',
                                                }}
                                                eventHandlers={!hasVoronoi ? {
                                                    mouseover: (e) => {
                                                        if (spotlight) return;
                                                        (e.target as L.Path).setStyle({ opacity: 0.9, fillOpacity: 0.18 });
                                                    },
                                                    mouseout: (e) => {
                                                        if (spotlight) return;
                                                        (e.target as L.Path).setStyle({ opacity: 0, fillOpacity: 0 });
                                                    },
                                                    click: () => {
                                                        handleOverlayClick(map.id, element.id, element.image_id);
                                                    },
                                                } : undefined}
                                            />
                                        );
                                    })}
                                    {/* Pass 2: Voronoi polygons (on top) — receive mouse events, update corner fill via ref */}
                                    {showPolygons && map.map_elements?.map((element) => {
                                        const voronoiCell = element.voronoi_gps;
                                        if (!voronoiCell || voronoiCell.length === 0) return null;
                                        const corners = element.corners.gps;
                                        const displayPolygon = polygonIntersection(voronoiCell, corners);
                                        //debug
                                        //const displayPolygon = voronoiCell //polygonIntersection(voronoiCell, corners);
                                        //const randomColor = `hsl(${Math.random() * 360}, 95%, 70%)`;
                                        return (
                                            <Polygon
                                                key={`map-${map.id}_voronoi-${element.id}`}
                                                positions={displayPolygon}
                                                pathOptions={{
                                                    className: 'map-footprint',
                                                    color: FOOTPRINT_COLOR,
                                                    weight: 2,
                                                    // color: 'yellow',
                                                    // weight: 4,
                                                    opacity: 0,
                                                    fillOpacity: 0,
                                                    lineJoin: 'round',
                                                }}
                                                eventHandlers={{
                                                    mouseover: (e) => {
                                                        if (spotlight) return;
                                                        (e.target as L.Path).setStyle({ opacity: 0.95 });
                                                        cornerRefs.current.get(element.id)?.setStyle({ fillOpacity: 0.18 });
                                                        // cornerRefs.current.get(element.id)?.setStyle({ fillOpacity: 0.18, opacity: 0.95 });
                                                    },
                                                    mouseout: (e) => {
                                                        if (spotlight) return;
                                                        (e.target as L.Path).setStyle({ opacity: 0 });
                                                        cornerRefs.current.get(element.id)?.setStyle({ fillOpacity: 0, opacity: 0 });
                                                    },
                                                    click: () => {
                                                        handleOverlayClick(map.id, element.id, element.image_id);
                                                    },
                                                }}
                                            />
                                        );
                                            // <>
                                            //     <Circle
                                            //     center={getCenter(element.corners.gps)}
                                            //     radius={1.3}
                                            //     pathOptions={{
                                            //         color: 'black',
                                            //         fillColor: 'white',
                                            //         weight: 2.35,
                                            //         fillOpacity: 1,
                                            //     }}
                                            // />
                                    })}
                                </LayerGroup>
                            </LayersControl.Overlay>
                        );
                    })}
                </LayersControl>

                {(bounds || center) && (
                    <HomeButton bounds={bounds} center={center} />
                )}

                {hasDetectionMarkers && (
                    <div
                        style={{
                            position: 'absolute',
                            top: '128px',
                            left: '12px',
                            zIndex: 1000,
                            borderRadius: '2px',
                            boxShadow: '0 1px 3px rgba(0,0,0,0.8)',
                        }}
                        className="flex flex-col overflow-hidden"
                    >
                        <button
                            type="button"
                            onClick={() => setSpatialClusterEnabled(v => !v)}
                            title={spatialClusterEnabled
                                ? "Spatial clustering on — click to disable"
                                : "Spatial clustering off — click to enable"}
                            aria-pressed={spatialClusterEnabled}
                            className="p-1 cursor-pointer hover:bg-gray-100 bg-white transition-colors duration-200"
                        >
                            {spatialClusterEnabled
                                ? <Group size={22} className="dark:text-black" />
                                : <Ungroup size={22} className="dark:text-black" />}
                        </button>
                        <div className="h-px bg-gray-300" />
                        <button
                            type="button"
                            onClick={() => setHighContrast(v => !v)}
                            title={highContrast
                                ? "High-contrast markers on — click for the default style"
                                : "High-contrast markers off — click to enable"}
                            aria-pressed={highContrast}
                            className={`p-1 cursor-pointer hover:bg-gray-100 transition-colors duration-200 ${highContrast ? "bg-gray-200" : "bg-white"}`}
                        >
                            <Contrast className={highContrast ? "[&>path]:fill-current dark:text-black" : "dark:text-black"}  size={22}/>
                        </button>
                    </div>
                )}
            </MapContainer>

            {(maps && maps.length !== 0) && (
                <div className="absolute left-1/2 bottom-2 transform -translate-x-1/2 z-10 bg-white dark:bg-gray-800 px-3 py-2 rounded-md shadow-md flex flex-row items-center h-14">
                    <div className="dlex flex-col items-center">
                        <label className="text-sm font-medium mb-1 block text-center">Overlay Opacity</label>
                        <Slider
                            defaultValue={[overlayOpacity]}
                            min={0}
                            max={1}
                            step={0.02}
                            onValueChange={(value) => setOverlayOpacity(value[0])}
                            className="py-1 w-40"
                        />
                    </div>
                    <Separator orientation="vertical" className="mx-4 h-6" />
                    <div className="flex flex-col items-center w-15">
                        <label className="text-sm font-medium mb-1 block text-center">Trajectory</label>
                        <Switch
                            checked={showTrajectory}
                            onCheckedChange={(checked) => setShowTrajectory(checked)}
                            className="w-8"
                        />
                    </div>
                    <Separator orientation="vertical" className="mx-4 h-6" />
                    {maps && maps.length > 0 && (
                        <div className="flex flex-col items-center w-15">
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <label className={`text-sm font-medium mb-1 block text-center ${spotlight ? "text-muted-foreground opacity-50" : ""}`}>Overlays</label>
                                </TooltipTrigger>
                                <TooltipContent>
                                    {spotlight
                                        ? "Overlays are inactive while a detection group is open"
                                        : "Toggle image footprint overlays"}
                                </TooltipContent>
                            </Tooltip>
                            <Switch
                                checked={showPolygons}
                                disabled={spotlight}
                                onCheckedChange={(checked) => setShowPolygons(checked)}
                                className="w-8"
                            />
                        </div>
                    )}
                    {(images && images.length > 0 && images.some(image => image.panoramic)) && (
                        <>
                            <Separator orientation="vertical" className="mx-4 h-6" />
                            <div className="flex flex-col items-center w-15">
                                <label className="text-sm font-medium mb-1 block text-center">Panos</label>
                                <Switch
                                    checked={showPanoMarkers}
                                    onCheckedChange={(checked) => setShowPanoMarkers(checked)}
                                    className="w-8"
                                />
                            </div>
                        </>
                    )}
                    {detections && detections.length > 0 && images && images.length > 0 && maps && maps.length > 0 && (
                        <>
                            <Separator orientation="vertical" className="mx-4 h-6" />
                            <div className="flex flex-col items-center w-15">
                                <label className="text-sm font-medium mb-1 block text-center">Detections</label>
                                <Switch
                                    checked={showDetections}
                                    onCheckedChange={(checked) => setShowDetections(checked)}
                                    className="w-8"
                                />
                            </div>
                        </>
                    )}
                    {hasFireOverlay && (
                        <>
                            <Separator orientation="vertical" className="mx-4 h-6" />
                            <div className="flex flex-col items-center w-18">
                                <div className="flex items-center gap-1 mb-1">
                                    <label className="text-sm font-medium block text-center">Fire</label>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <CircleHelp size={14} className="text-muted-foreground cursor-help" />
                                        </TooltipTrigger>
                                        <TooltipContent className="max-w-56">
                                            <p>
                                                Areas with potential fire, merged from all fire
                                                detections in the color images. Detection confidence indicated by color:
                                            </p>
                                            <div
                                                className="h-2 w-full rounded my-1"
                                                style={{ background: CONFIDENCE_RAMP_GRADIENT }}
                                            />
                                            <div className="flex justify-between leading-tight">
                                                <span>low</span>
                                                <span>high</span>
                                            </div>
                                            <p className="mt-1">Click a region to see where it was detected.</p>
                                        </TooltipContent>
                                    </Tooltip>
                                </div>
                                <Switch
                                    checked={showFireMap}
                                    onCheckedChange={(checked) => setShowFireMap(checked)}
                                    className="w-8"
                                />
                            </div>
                        </>
                    )}
                    {hasThermalCapable && (
                        <>
                            <Separator orientation="vertical" className="mx-4 h-6" />
                            <div className="flex flex-col items-center w-18">
                                <div className="flex items-center gap-1 mb-1">
                                    <label className="text-sm font-medium block text-center">Temperature</label>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <CircleHelp size={14} className="text-muted-foreground cursor-help" />
                                        </TooltipTrigger>
                                        <TooltipContent className="max-w-56">
                                            <p>
                                                Thermal images merged into one temperature map
                                                (hottest reading wins where they overlap), drawn in
                                                10 °C bands{thermalMap?.range ? ` — this report spans ${thermalMap.range.min} to ${thermalMap.range.max} °C` : ""}:
                                            </p>
                                            <div
                                                className="h-2 w-full rounded my-1"
                                                style={{ background: TEMPERATURE_RAMP_GRADIENT }}
                                            />
                                            <div className="flex justify-between leading-tight">
                                                <span>cold</span>
                                                <span>hot</span>
                                            </div>
                                            <p className="mt-1">
                                                The gallery's temperature filters clip what is shown;
                                                colors re-fit to the filtered range (a hotter filter
                                                floor starts higher on the ramp, never at cold).
                                                Click a region to see which images cover it.
                                            </p>
                                        </TooltipContent>
                                    </Tooltip>
                                </div>
                                <Switch
                                    checked={showTempMap}
                                    onCheckedChange={(checked) => setShowTempMap(checked)}
                                    className="w-8"
                                />
                            </div>
                        </>
                    )}

                </div>
            )}

            <AssignObjectDialog
                reportId={reportId}
                open={editDetection != null}
                onOpenChange={(o) => { if (!o) setEditDetection(null); }}
                detection={editDetection}
            />
        </div>
    );
}


function HomeButton({ bounds, center }: { bounds: LatLngBoundsExpression | null, center: LatLngBoundsExpression }) {
    const map = useMap();
    if (!map && !bounds) return null;

    const homeMap = () => {
        if (bounds) {
            map.fitBounds(bounds);
        } else if (center) {
            map.setView(center, 18.5);
        }
    };

    return (
        <div
            style={{
                position: 'absolute',
                top: '84px',
                left: '12px',
                zIndex: 1000,
                padding: '4px',
                borderRadius: '2px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.8)',
                cursor: 'pointer'
            }}
            className="hover:bg-gray-100 bg-white transition-colors duration-200"
            title="Reset View"
            onClick={() => homeMap()}
        >
            <Home size={22} className="dark:text-black" />
        </div>
    );
}

export const MapTab = React.memo(MapTabComponent);
