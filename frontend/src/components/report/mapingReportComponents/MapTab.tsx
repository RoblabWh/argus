import { useState, useEffect, useRef, useMemo } from "react";
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
    Circle,
    useMap
} from 'react-leaflet';
import { useTheme } from "@/components/ui/theme-provider";
import type { LatLngBoundsExpression, Map as LeafletMap } from 'leaflet';
import L, { bounds, } from "leaflet";
import 'leaflet/dist/leaflet.css';
import { Slider } from "@/components/ui/slider";
import "@/lib/Leaflet.ImageOverlay.Rotated";
import { RotatedImageOverlay } from "@/components/report/mapingReportComponents/RotatedImageOverlay";

interface Props {
    report: Report;
    selectImageOnMap: (image_id: number) => void;
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


export function MapTab({ report, selectImageOnMap }: Props) {
    const [overlayOpacity, setOverlayOpacity] = useState(1.0);
    const [map, setMap] = useState<LeafletMap | null>(null);

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


    const bounds = useMemo(() => {
        if (!report?.mapping_report?.maps?.length) return null;

        const gps = report.mapping_report.maps[0].bounds.gps;
        return [
            [gps.latitude_min, gps.longitude_min],
            [gps.latitude_max, gps.longitude_max]
        ] as LatLngBoundsExpression;
    }, [report]);


    const handleOverlayClick = (mapId: number, elementId: string, image_id: string) => {
        selectImageOnMap(image_id)
    };

    // useEffect(() => {
    //     map?.eachLayer((layer) => {
    //         if (layer instanceof L.ImageOverlay) {
    //             layer.setOpacity(overlayOpacity);
    //         }
    //     });
    //     console.log("this is called:", overlayOpacity);
    // }, [overlayOpacity]);


    useEffect(() => {
        console.log("Map created, bounds are:", bounds);
        if (map !== null && bounds) {
            map.fitBounds(bounds);
        }
    }, [map]);

    useEffect(() => {
        console.log("Map component mounted, current theme is:", current);
        if (map !== null) {
            // new resize Observer to handle map resizing
            const resizeObserver = new ResizeObserver(() => {
                if (!map) return;
                try {
                    console.log("Resizing map observer triggered");
                    map.invalidateSize();
                    // map.flyTo(map.getCenter(), map.getZoom());
                } catch (error) {
                    return
                }
            });
            resizeObserver.observe(map.getContainer());
        }
    }, [map]);

    useEffect(() => {
        if (map !== null && bounds) {
            map.fitBounds(bounds);
        }
    }, [map, bounds]);

    return (
        <div className="w-full h-full relative">
            <MapContainer center={center} zoom={18.5} ref={setMap} style={{ zIndex: 0, flex: 1, height: '100%' }}>
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

                                    {useRotatedOverlay ? (
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

                                    {/* {bounds_corners.map((corner, index) => (
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
                                ))} */}

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

                {(bounds || center) && (
                    <HomeButton bounds={bounds} center={center} />
                )}
            </MapContainer>

            {(report.mapping_report?.maps && report.mapping_report.maps.length !== 0) && (
                <div className="absolute left-1/2 bottom-2 transform -translate-x-1/2 z-10 bg-white dark:bg-gray-800 px-3 py-2 rounded-md shadow-md flex flex-col items-center">
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
            )}
        </div>


    );
}


// import { useMap } from 'react-leaflet';
import { Home } from 'lucide-react'; // optional icon lib

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