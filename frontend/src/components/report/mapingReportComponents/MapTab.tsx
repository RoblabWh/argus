import { useState, useEffect, useRef } from "react";
import type { Report } from "@/types/report";
import type { Image } from "@/types/image";
import { getApiUrl } from "@/api";
import {
    MapContainer,
    TileLayer,
    LayersControl,
    ImageOverlay,
    Marker,
    Popup,
    Rectangle,
    Polygon,
    Polyline,
    LayerGroup,
    Circle
} from 'react-leaflet';
import { useTheme } from "@/components/ui/theme-provider";
import type { LatLngBoundsExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Slider } from "@/components/ui/slider";
import "@/lib/Leaflet.ImageOverlay.Rotated";
import L from "leaflet";
import { RotatedImageOverlay } from "@/components/report/mapingReportComponents/RotatedImageOverlay";

interface Props {
    report: Report;
}

const { BaseLayer, Overlay } = LayersControl;

function extractFlightTrajectory(images: Image[]) {
    //sort all images by created_at
    images.sort((a, b) => (a.created_at ? new Date(a.created_at).getTime() : 0) - (b.created_at ? new Date(b.created_at).getTime() : 0));
    //collect gps coordinates from images and put them in a list of [lat, lon] pairs
    const flightPath = images.map((image) => {
        if (!image.coord || !image.coord.gps || image.coord.gps === undefined) return null;
        return [image.coord.gps.lat, image.coord.gps.lon];
    }).filter(Boolean) as LatLngBoundsExpression;

    return flightPath;
}


export function MapTab({ report }: Props) {
    const [overlayOpacity, setOverlayOpacity] = useState(1.0);
    const api_url = getApiUrl();
    const { theme } = useTheme();
    const current = theme === "system"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light"
        : theme;    //Check if report has maps, If not show overlay over map (that can be closed by clicking, but since no gps data is available the map will start ata default location (in fututre editable in settins))

    const first_image_with_gps = report.mapping_report?.images?.find((image) => image.coord);
    const first_map = report.mapping_report?.maps?.[0] || null;
    const center = first_map
        ? [(first_map.bounds.gps.latitude_min + first_map.bounds.gps.latitude_max) / 2, (first_map.bounds.gps.longitude_min + first_map.bounds.gps.longitude_max) / 2]
        : (first_image_with_gps ? [first_image_with_gps.coord.gps.lat, first_image_with_gps.coord.gps.lon] : [51.574, 7.027]);

    const overlayRefs = useRef<Record<string, L.ImageOverlay | null>>({});
    useEffect(() => {
        Object.values(overlayRefs.current).forEach((overlay) => {
            if (overlay) {
                overlay.setOpacity(overlayOpacity);
            }
        });
    }, [overlayOpacity]);

    const handleOverlayClick = (mapId: number, elementId: string, image_id: string) => {
        console.log(`Clicked overlay from map ${mapId}, element ${elementId}, with image ${image_id}`);
    };

    return (
        <MapContainer center={center} zoom={18} style={{ zIndex: 0, flex: 1, height: '100%' }}>
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

                {report.mapping_report?.images && report.mapping_report?.images.length > 0 && (
                    <Overlay name="Flight Trajectory" checked>
                        <LayerGroup>
                            <Polyline
                                positions={extractFlightTrajectory(report.mapping_report.images)}
                                pathOptions={{ color: 'magenta', weight: 2, opacity: 1 }}
                            />
                        </LayerGroup>
                    </Overlay>
                )}

                {report.mapping_report?.maps?.map((map) => {
                    const { latitude_min, latitude_max, longitude_min, longitude_max } = map.bounds.gps;
                    let useRotatedOverlay = false;
                    let gps_corners: LatLngBoundsExpression[] = [];

                    const bounds: LatLngBoundsExpression = [
                        [latitude_min, longitude_min],
                        [latitude_max, longitude_max],
                    ];

                    const bounds_corners = [
                        [latitude_min, longitude_min],
                        [latitude_min, longitude_max],
                        [latitude_max, longitude_max],
                        [latitude_max, longitude_min],
                    ];

                    if (!map.bounds.corners || map.bounds.corners.gps.length < 4) {
                        console.warn(`Map ${map.name} does not have enough corners defined, using default bounds.`);
                        useRotatedOverlay = false;
                        
                    } else {
                        useRotatedOverlay = true;
                        gps_corners = map.bounds.corners.gps.map((corner: LatLngBoundsExpression) => ([corner[1], corner[0]]));
                    }

                    return (
                        <Overlay key={map.name} name={`Map: ${map.name}`} checked>
                            <LayerGroup>
                                { useRotatedOverlay ? (
                                <RotatedImageOverlay
                                    url={`${api_url}/${map.url}`}
                                    corners={[
                                        gps_corners[0], // top-left
                                        gps_corners[1], // top-right
                                        gps_corners[3], // bottom-left
                                    ]}
                                    opacity={overlayOpacity}
                                />) : (
                                    <ImageOverlay
                                        url={`${api_url}/${map.url}`}
                                        bounds={bounds}
                                        opacity={overlayOpacity}
                                    />
                                )}

                                {bounds_corners.map((corner, index) => (
                                    <Circle
                                        key={`map-${map.id}_corner-${index}`}
                                        center={corner}
                                        radius={1}
                                        color="red"
                                    />
                                ))}

                                {gps_corners.map((corner, index) => (
                                    <Circle
                                        key={`map-${map.id}_corner-${index}`}
                                        center={corner}
                                        radius={1}
                                        color="green"
                                    />
                                ))}

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
                                                    // later: open slideshow here
                                                },
                                            }}
                                        />
                                    );
                                })}
                            </LayerGroup>
                        </Overlay>

                    );
                })}
            </LayersControl>
            {(report.mapping_report?.maps && report.mapping_report.maps.length !== 0) && (
            <div style={{
                position: 'absolute',
                bottom: '1rem',
                left: '50%',
                transform: 'translateX(-50%)',
                zIndex: 1000,
                padding: '0.5rem 1rem',
                backgroundColor: theme === "dark" ? '#123' : '#fff',
                borderRadius: '0.5rem'
            }}>
                <label className="text-sm font-medium mb-1 block text-center">Overlay Opacity</label>
                <Slider
                    defaultValue={[overlayOpacity]}
                    min={0}
                    max={1}
                    step={0.02}
                    onValueChange={(value) => setOverlayOpacity(value[0])}
                />
            </div>
            )}
        </MapContainer>


    );
}
