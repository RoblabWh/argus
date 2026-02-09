import React from "react";
import { useState, useEffect, useMemo } from "react";
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
import { extractFlightTrajectory, computeDetectionGps } from "@/utils/coordinateUtils";

// Re-export for backward compatibility if other components import from here
export { extractFlightTrajectory } from "@/utils/coordinateUtils";

const { BaseLayer } = LayersControl;

interface Props {
    reportId: number;
    selectImageOnMap: (image_id: number) => void;
    thresholds: { [key: string]: number };
    visibleCategories: { [key: string]: boolean };
    visibleMapOverlays: { [mapId: number]: boolean };
    setVisibleMapOverlays: (overlays: { [mapId: number]: boolean }) => void;
}

function MapTabComponent({ reportId, selectImageOnMap, thresholds, visibleCategories, visibleMapOverlays, setVisibleMapOverlays }: Props) {
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

    // Cache detection icons by class name - avoids creating new icon objects on every render
    const detectionIconCache = useMemo(() => {
        const cache = new Map<string, L.DivIcon>();
        const getIcon = (className: string) => {
            if (!cache.has(className)) {
                cache.set(className, L.divIcon({
                    className: 'custom-div-icon',
                    html: `<div style="background-color:${getDetectionColor(className)};opacity:0.85;width:12px;height:12px;border-radius:50%;border:2px solid black;"></div>`,
                    iconSize: [16, 16],
                    iconAnchor: [8, 8],
                    popupAnchor: [0, -8],
                }));
            }
            return cache.get(className)!;
        };
        return getIcon;
    }, []);

    // Memoize filtered detections with their GPS coordinates pre-computed
    const visibleDetections = useMemo(() => {
        if (!detections?.length || !images?.length || !maps?.length) return [];

        return detections
            .filter(det =>
                visibleCategories[det.class_name] &&
                det.score >= (thresholds[det.class_name] || 0)
            )
            .map(det => {
                const gps = det.coord?.gps || computeDetectionGps(det, images, maps);
                return gps ? { ...det, computedGps: gps } : null;
            })
            .filter(Boolean) as (Detection & { computedGps: GPSCoord })[];
    }, [detections, images, maps, visibleCategories, thresholds]);

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

    const handleOverlayClick = (mapId: number, elementId: string, image_id: number) => {
        selectImageOnMap(image_id);
    };

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
                                pathOptions={{ color: 'magenta', weight: 2, opacity: 1 }}
                            />
                        </LayerGroup>
                    )}
                    {visibleDetections.length > 0 && showDetections && (
                        <LayerGroup>
                            {visibleDetections.map(detection => (
                                <Marker
                                    key={detection.id}
                                    position={[detection.computedGps.lat, detection.computedGps.lon]}
                                    icon={detectionIconCache(detection.class_name)}
                                >
                                    <Popup>
                                        <div className="w-36">
                                            <strong>{detection.class_name}</strong><br />
                                            Confidence: {(detection.score * 100).toFixed(1)}%<br />
                                            Image ID: {detection.image_id}
                                            <Button onClick={() => {
                                                selectImageOnMap(detection.image_id);
                                            }} className="text-sm w-full mt-2">Show</Button>
                                        </div>
                                    </Popup>
                                </Marker>
                            ))}
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

                                    {map.map_elements?.map((element) => {
                                        const corners = element.corners.gps;

                                        return (
                                            <Polygon
                                                key={`map-${map.id}_element-${element.id}`}
                                                positions={[
                                                    corners[0],
                                                    corners[1],
                                                    corners[2],
                                                    corners[3],
                                                ]}
                                                pathOptions={{
                                                    color: 'blue',
                                                    weight: 1,
                                                    fillOpacity: 0,
                                                    stroke: false,
                                                }}
                                                eventHandlers={{
                                                    mouseover: (e) => {
                                                        const layer = e.target as L.Path;
                                                        layer.setStyle({ fillOpacity: 0.2 });
                                                    },
                                                    mouseout: (e) => {
                                                        const layer = e.target as L.Path;
                                                        layer.setStyle({ fillOpacity: 0 });
                                                    },
                                                    click: () => {
                                                        handleOverlayClick(map.id, element.id, element.image_id);
                                                    },
                                                }}
                                            />
                                        );
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
