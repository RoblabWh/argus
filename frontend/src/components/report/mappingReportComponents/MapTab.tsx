import React from "react";
import { useState, useEffect, useMemo, useRef } from "react";
import type { ImageBasic, GPSCoord } from "@/types/image";
import type { Detection } from "@/types/detection";
import { getDetectionColor } from "@/types/detection";
import { getApiUrl } from "@/api";
import {
    MapContainer,
    TileLayer,
    LayersControl,
    ImageOverlay,
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
import { Home } from 'lucide-react';
import "@/lib/Leaflet.ImageOverlay.Rotated";
import { RotatedImageOverlay } from "@/components/report/mappingReportComponents/RotatedImageOverlay";
import panoPinSVG from '@/assets/panorama.svg';
import { useImages } from "@/hooks/imageHooks";
import { useMaps } from "@/hooks/useMaps";
import { useDetections, useUpdateDetectionBatch } from "@/hooks/detectionHooks";
import { extractFlightTrajectory, computeDetectionGps, isPointInPolygon, polygonIntersection } from "@/utils/coordinateUtils";
import { groupDetectionsByObject } from "@/utils/detectionUtils";
import { AssignObjectDialog } from "@/components/report/mappingReportComponents/AssignObjectDialog";

// Re-export for backward compatibility if other components import from here
export { extractFlightTrajectory } from "@/utils/coordinateUtils";

const { BaseLayer } = LayersControl;

// Cluster count badges are hidden below this zoom (too cluttered when zoomed out)
const CLUSTER_BADGE_MIN_ZOOM = 20;

// Accent for image-footprint overlay polygons (reads on light + dark basemaps)
const FOOTPRINT_COLOR = "#0ea5e9"; // sky-500

type DetectionWithGps = Detection & { computedGps: GPSCoord };
type ClusterMarker = {
    uid: number;
    members: DetectionWithGps[];
    centroid: GPSCoord;
    className: string;
};

/** Radius in meters that encloses a cluster's members around its centroid (with padding). */
function clusterRadiusMeters(cluster: ClusterMarker): number {
    const { lat, lon } = cluster.centroid;
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
    clipDetections: boolean;
    setClipDetections: (v: boolean) => void;
    selectedObjectId: number | null;
    setSelectedObjectId: (id: number | null) => void;
}

function MapTabComponent({ reportId, selectImageOnMap, thresholds, visibleCategories, visibleMapOverlays, setVisibleMapOverlays, clipDetections, selectedObjectId, setSelectedObjectId }: Props) {
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
                const color = getDetectionColor(className);
                const size = highlighted ? 10 : 8;
                const shadow = highlighted
                    ? `0 0 0 3px ${color}80, 0 1px 4px rgba(0,0,0,0.5)`
                    : `0 1px 3px rgba(0,0,0,0.45)`;
                cache.set(key, L.divIcon({
                    className: 'custom-div-icon',
                    html: `<div class="marker-dot" style="background-color:${color};width:${size}px;height:${size}px;border-radius:50%;border:3px solid #fff;box-shadow:${shadow};box-sizing:border-box;"></div>`,
                    iconSize: [size, size],
                    iconAnchor: [size / 2, size / 2],
                    popupAnchor: [0, -size / 2],
                }));
            }
            return cache.get(key)!;
        };
        return getIcon;
    }, []);

    // Build a lookup from image_id → Voronoi polygon (GPS coords)
    const voronoiIndex = useMemo(() => {
        const index = new Map<number, [number, number][]>();
        maps?.forEach(m =>
            m.map_elements?.forEach(el => {
                if (el.voronoi_gps?.length) index.set(el.image_id, el.voronoi_gps);
            })
        );
        return index;
    }, [maps]);

    // Cache merged-cluster icons by class + count + whether the count badge is shown (zoom-gated)
    const getClusterIcon = useMemo(() => {
        const cache = new Map<string, L.DivIcon>();
        return (className: string, count: number, showBadge: boolean) => {
            const key = `${className}|${count}|${showBadge ? 1 : 0}`;
            if (!cache.has(key)) {
                const color = getDetectionColor(className);
                const centerColor = getDetectionColor(className, true);
                const badge = showBadge
                    ? `<span style="position:absolute;top:-7px;right:-7px;background:#111;color:#fff;border-radius:9px;font-size:10px;line-height:14px;min-width:14px;height:14px;text-align:center;padding:0 2px;border:1px solid #fff;box-sizing:border-box;">${count}</span>`
                    : "";
                cache.set(key, L.divIcon({
                    className: 'custom-div-icon',
                    html: `<div style="position:relative;width:16px;height:16px;">
                        <div class="marker-dot" style="background-color:${centerColor};width:10px;height:10px;border-radius:50%;border:2px solid ${color};box-shadow:0 1px 4px rgba(0,0,0,0.5);box-sizing:border-box;"></div>
                        ${badge}
                    </div>`,
                    iconSize: [22, 22],
                    iconAnchor: [11, 11],
                    popupAnchor: [0, -11],
                }));
            }
            return cache.get(key)!;
        };
    }, []);

    // Threshold/visibility-filtered detections with GPS, split into re-id clusters
    // (merged) and unassigned (rendered individually, with Voronoi clip preserved).
    const { clusters, unassignedVisible } = useMemo(() => {
        if (!detections?.length || !images?.length || !maps?.length) {
            return { clusters: [] as ClusterMarker[], unassignedVisible: [] as DetectionWithGps[] };
        }

        const withGps = detections
            .filter(det =>
                visibleCategories[det.class_name] &&
                det.score >= (thresholds[det.class_name] || 0)
            )
            .map(det => {
                const gps = det.coord?.gps || computeDetectionGps(det, images, maps);
                return gps ? { ...det, computedGps: gps } : null;
            })
            .filter(Boolean) as DetectionWithGps[];

        const { clusters: rawClusters, unassigned } = groupDetectionsByObject(withGps);

        // One merged marker per cluster at the centroid of its members (no clip — we
        // intentionally merge the overlapping duplicates).
        const clusterList: ClusterMarker[] = Array.from(rawClusters.entries()).map(([uid, members]) => {
            const lat = members.reduce((s, m) => s + m.computedGps.lat, 0) / members.length;
            const lon = members.reduce((s, m) => s + m.computedGps.lon, 0) / members.length;
            return { uid, members, centroid: { lat, lon }, className: members[0].class_name };
        });

        // Unassigned detections keep the existing per-image Voronoi clip behavior.
        const unassignedVisible = unassigned.filter(det => {
            if (!clipDetections) return true;
            const voronoi = voronoiIndex.get(det.image_id);
            if (!voronoi) return true;  // no Voronoi data → always show
            return isPointInPolygon([det.computedGps.lat, det.computedGps.lon], voronoi);
        });

        return { clusters: clusterList, unassignedVisible };
    }, [detections, images, maps, visibleCategories, thresholds, clipDetections, voronoiIndex]);

    const hasDetectionMarkers = clusters.length > 0 || unassignedVisible.length > 0;

    // Spotlight: when a cluster is selected, fade everything that isn't its children
    const spotlight = selectedObjectId != null;
    const selectedCluster = spotlight ? clusters.find(c => c.uid === selectedObjectId) : undefined;
    
    const getCenter = (corners: [number, number][]): [number, number] => {
        const lat = (corners[0][0] + corners[1][0] + corners[2][0] + corners[3][0]) / 4;    
        const lon = (corners[0][1] + corners[1][1] + corners[2][1] + corners[3][1]) / 4;
        return [lat, lon];
    }

    useEffect(() => {
        let first_image_with_gps = images?.find((image) => image.coord);
        if (first_image_with_gps && first_image_with_gps.coord?.gps) {
            setCenter([first_image_with_gps.coord.gps.lat, first_image_with_gps.coord.gps.lon]);
            map?.setView([first_image_with_gps.coord.gps.lat, first_image_with_gps.coord.gps.lon], 18);
        }
    }, [images]);

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

    const handleOverlayClick = (mapId: number, elementId: number, image_id: number) => {
        selectImageOnMap(image_id);
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

    useEffect(() => {
        if (map !== null && bounds) {
            map.fitBounds(bounds);
        }
    }, [map]);

    useEffect(() => {
        if (!detections?.length || !images?.length || !maps?.length) return;

        // Find detections missing GPS
        const toUpdate = detections
            .filter(det => !det.coord?.gps?.lat || !det.coord?.gps?.lon)
            .map(det => {
                const gps = computeDetectionGps(det, images, maps);
                if (!gps) return null;
                det.coord = { gps: gps, utm: undefined };
                return det;
            })
            .filter(Boolean);

        // Send a single batch PUT if needed
        if (toUpdate.length > 0 && toUpdate !== null && updateDetections) {
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
        const handler = () => setSelectedObjectId(null);
        map.on("click", handler);
        return () => { map.off("click", handler); };
    }, [map, setSelectedObjectId]);

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
                                    center={[selectedCluster.centroid.lat, selectedCluster.centroid.lon]}
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

                            {/* Unassigned detections — individual markers (clicking clears any cluster selection) */}
                            {unassignedVisible.map(detection => (
                                <Marker
                                    key={`det-${detection.id}`}
                                    position={[detection.computedGps.lat, detection.computedGps.lon]}
                                    icon={detectionIconCache(detection.class_name)}
                                    opacity={spotlight ? 0.3 : 1}
                                    eventHandlers={{ click: () => setSelectedObjectId(null) }}
                                >
                                    {renderDetectionPopup(detection)}
                                </Marker>
                            ))}

                            {/* Re-id clusters — one merged marker per object; expands to child markers when selected */}
                            {clusters.map(cluster => {
                                if (cluster.uid === selectedObjectId) {
                                    // Selected: show the individual member detections (highlighted) instead of the merged marker
                                    return cluster.members.map(member => (
                                        <Marker
                                            key={`obj-${cluster.uid}-det-${member.id}`}
                                            position={[member.computedGps.lat, member.computedGps.lon]}
                                            icon={detectionIconCache(member.class_name, true)}
                                        >
                                            {renderDetectionPopup(member)}
                                        </Marker>
                                    ));
                                }
                                return (
                                    <Marker
                                        key={`obj-${cluster.uid}`}
                                        position={[cluster.centroid.lat, cluster.centroid.lon]}
                                        icon={getClusterIcon(cluster.className, cluster.members.length, zoom >= CLUSTER_BADGE_MIN_ZOOM)}
                                        opacity={spotlight ? 0.3 : 1}
                                        eventHandlers={{ click: () => setSelectedObjectId(cluster.uid) }}
                                    />
                                );
                            })}
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
                                                    color: FOOTPRINT_COLOR,
                                                    fillColor: FOOTPRINT_COLOR,
                                                    weight: 2,
                                                    opacity: 0,
                                                    fillOpacity: 0,
                                                    lineJoin: 'round',
                                                }}
                                                eventHandlers={!hasVoronoi ? {
                                                    mouseover: (e) => {
                                                        (e.target as L.Path).setStyle({ opacity: 0.9, fillOpacity: 0.18 });
                                                    },
                                                    mouseout: (e) => {
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
                                                    opacity: 0,
                                                    fillOpacity: 0,
                                                    lineJoin: 'round',
                                                }}
                                                eventHandlers={{
                                                    mouseover: (e) => {
                                                        (e.target as L.Path).setStyle({ opacity: 0.95 });
                                                        cornerRefs.current.get(element.id)?.setStyle({ fillOpacity: 0.18 });
                                                    },
                                                    mouseout: (e) => {
                                                        (e.target as L.Path).setStyle({ opacity: 0 });
                                                        cornerRefs.current.get(element.id)?.setStyle({ fillOpacity: 0 });
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
                            <label className="text-sm font-medium mb-1 block text-center">Overlays</label>
                            <Switch
                                checked={showPolygons}
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
