import { useState, useMemo, useRef, useEffect } from "react";
import {
    MapContainer,
    TileLayer,
    ImageOverlay,
    LayerGroup,
    LayersControl
} from "react-leaflet";
import type { LatLngBoundsExpression, Map as LeafletMap } from 'leaflet';
import { getApiUrl } from "@/api";
import { useTheme } from "@/components/ui/theme-provider";
import { RotatedImageOverlay } from "@/components/report/mapingReportComponents/RotatedImageOverlay";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { Home, Map } from "lucide-react";
import type { ReportSummary } from "@/types/report";
import "leaflet/dist/leaflet.css";
import { createRoot } from "react-dom/client";
import { useMap } from 'react-leaflet';
import { Map as MapIcon, Layers } from "lucide-react";
import { Separator } from "@/components/ui/separator";



const { BaseLayer } = LayersControl;

export function GroupMapTab({
    summaryReports = []
}: {
    summaryReports: ReportSummary[];
}) {
    const api_url = getApiUrl();
    const [isLayerControlExpanded, setIsLayerControlExpanded] = useState(false);
    const hideTimer = useRef<NodeJS.Timeout | null>(null);
    const [leafletMap, setLeafletMap] = useState<LeafletMap | null>(null);
    const { theme } = useTheme();
    const hasAnyMaps = summaryReports.some((r) => (r.maps?.length ?? 0) > 0);
    const containerSize = useMemo(() => {
        const width = window.innerWidth;
        const height = window.innerHeight;
        return { width, height };
    }, [window.innerWidth, window.innerHeight]);

    if (summaryReports.length > 0) {
        summaryReports.sort((a, b) => {
            const dateA = new Date(a.created_at);
            const dateB = new Date(b.created_at);
            return dateA.getTime() - dateB.getTime(); // Sort by created_at descending
        });
    }

    const current = theme === "system"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light"
        : theme;    //Check if report has maps, If not show overlay over map (that can be closed by clicking, but since no gps data is available the map will start ata default location (in fututre editable in settins))


    const showPanel = () => {
        if (hideTimer.current) {
            clearTimeout(hideTimer.current);
            hideTimer.current = null;
        }
        setIsLayerControlExpanded(true);
    };

    const hidePanel = () => {
        // Small delay to allow moving between icon and panel
        hideTimer.current = setTimeout(() => {
            setIsLayerControlExpanded(false);
        }, 150);
    };

    const [reportOpacity, setReportOpacity] = useState<Record<number, number>>(
        () => Object.fromEntries(summaryReports.map((r) => [r.report_id, 1]))
    );


    const [enabledMaps, setEnabledMaps] = useState<Record<string, boolean>>(() => {
        if (summaryReports.length === 0) return {};
        return Object.fromEntries(
            summaryReports.flatMap((r, i) =>
                (r.maps || []).map((m) => [
                    `${r.report_id}:${m.id}`,
                    i === 0 || i === summaryReports.length - 1, 
                ])
            )
        );
    });


    const overallBounds = useMemo(() => {
        const allMaps = summaryReports.flatMap((r) => r.maps || []);
        if (allMaps.length) {

            let latMin = Infinity,
                latMax = -Infinity,
                lonMin = Infinity,
                lonMax = -Infinity;

            allMaps.forEach((map) => {
                latMin = Math.min(latMin, map.bounds.gps.latitude_min);
                latMax = Math.max(latMax, map.bounds.gps.latitude_max);
                lonMin = Math.min(lonMin, map.bounds.gps.longitude_min);
                lonMax = Math.max(lonMax, map.bounds.gps.longitude_max);
            });

            return [
                [latMin, lonMin],
                [latMax, lonMax]
            ] as LatLngBoundsExpression;
        }
        const coords = summaryReports
            .map((r) => r.coord) // assumes shape like { lat, lon } or similar
            .filter((c): c is { lat: number; lon: number } => !!c);

        if (coords.length) {
            let latMin = Math.min(...coords.map((c) => c.gps.lat));
            let latMax = Math.max(...coords.map((c) => c.gps.lat));
            let lonMin = Math.min(...coords.map((c) => c.gps.lon));
            let lonMax = Math.max(...coords.map((c) => c.gps.lon));

            if (latMin === Infinity || latMax === -Infinity || lonMin === Infinity || lonMax === -Infinity) {
                return null; // No valid coordinates found
            }
            if (latMin === latMax || lonMin === lonMax) {
                // If all coordinates are the same, return a small bounds around that point
                const padding = 0.0003; // 30 meters approx
                latMin -= padding;
                latMax += padding;
                lonMin -= padding;
                lonMax += padding;
            }
            return [
                [latMin, lonMin],
                [latMax, lonMax]
            ] as LatLngBoundsExpression;
        }

        return null;
    }, [summaryReports]);

    const center = useMemo(() => {
        if (overallBounds) {
            const [[latMin, lonMin], [latMax, lonMax]] = overallBounds;
            return [(latMin + latMax) / 2, (lonMin + lonMax) / 2] as [number, number];
        }
        return [51.574, 7.027] as [number, number];
    }, [overallBounds]);


    useEffect(() => {
        console.log("Map component mounted, current theme is:", current);
        if (leafletMap !== null) {
            // new resize Observer to handle map resizing
            const resizeObserver = new ResizeObserver(() => {
                if (!leafletMap) return;
                try {
                    console.log("Resizing map observer triggered");
                    leafletMap.invalidateSize();
                    // leafletMap.flyTo(leafletMap.getCenter(), leafletMap.getZoom());
                } catch (error) {
                    return
                }
            });
            resizeObserver.observe(leafletMap.getContainer());
        }
    }, [leafletMap]);

    useEffect(() => {
        if (leafletMap !== null && overallBounds) {
            leafletMap.fitBounds(overallBounds);
        }
    }, [leafletMap, overallBounds]);

    const handleToggleLayer = (reportId: number, mapId: number, visible: boolean) => {
        if (mapId === -1) {
            // Toggle all maps for this report
            const newEnabledMaps = { ...enabledMaps };
            summaryReports.find((r) => r.report_id === reportId)?.maps.forEach((m) => {
                newEnabledMaps[`${reportId}:${m.id}`] = visible;
            });
            setEnabledMaps(newEnabledMaps);
            return;
        }
       
        setEnabledMaps((prev) => ({
            ...prev,
            [`${reportId}:${mapId}`]: visible
        }));
        console.log(enabledMaps);

    };

    const handleChangeOpacity = (reportId: number, opacity: number) => {
        setReportOpacity((prev) => ({
            ...prev,
            [reportId]: opacity
        }));
    };

    return (
        <div style={{ position: "relative", height: "100%", width: "100%" }} >
            <MapContainer center={center} zoom={18} style={{ height: "100%", width: "100%" }} ref={setLeafletMap}>
                <CustomLayerControl position="topright">
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
                </CustomLayerControl>

                {summaryReports.map((report) =>
                    (report.maps || []).map((mapData) => {
                        const key = `${report.report_id}:${mapData.id}`;
                        if (!enabledMaps[key]) return null;

                        const { latitude_min, latitude_max, longitude_min, longitude_max } =
                            mapData.bounds.gps;

                        const bounds: LatLngBoundsExpression = [
                            [latitude_min, longitude_min],
                            [latitude_max, longitude_max]
                        ];

                        let useRotated = false;
                        let gpsCorners: LatLngBoundsExpression[] = [];

                        if (mapData.bounds.corners?.gps?.length === 4) {
                            useRotated = true;
                            gpsCorners = mapData.bounds.corners.gps.map(
                                (corner) => [corner[1], corner[0]] as [number, number]
                            );
                        }

                        return (
                            <LayerGroup key={key}>
                                {useRotated ? (
                                    <RotatedImageOverlay
                                        url={`${api_url}/${mapData.url}`}
                                        corners={[gpsCorners[0], gpsCorners[1], gpsCorners[3]]}
                                        opacity={reportOpacity[report.report_id] ?? 1}
                                    />
                                ) : (
                                    <ImageOverlay
                                        url={`${api_url}/${mapData.url}`}
                                        bounds={bounds}
                                        opacity={reportOpacity[report.report_id] ?? 1}
                                    />
                                )}
                            </LayerGroup>
                        );
                    })
                )}
            </MapContainer>

            {/* Overlay Control Panel */}
            {hasAnyMaps && (<div className="absolute top-16 right-3 z-400"
                onMouseEnter={showPanel}
                onMouseLeave={hidePanel}>
                {!isLayerControlExpanded ? (
                    <div className={`flex items-center bg-white p-2 m-0 rounded-sm shadow-sm/80 hover:bg-gray-100 transition-colors ${containerSize.width < 480 ? 'mt-2' : ''}`}>
                        <Layers className={`${containerSize.width < 480 ? 'w-8 h-8' : 'w-7 h-7'} dark:text-gray-700 text-gray-700`} />
                    </div>
                ) : (
                    <Card className="w-72 max-h-[80vh] overflow-y-auto">
                        <CardHeader>
                            <CardTitle>Map Overlays</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {summaryReports.map((report) => (
                                report.maps.length > 0 && (
                                    <>
                                        <Separator orientation="horizontal" className="my-2" />
                                        <div key={report.report_id} className="mb-4">
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    checked={(report.maps.every((m) => enabledMaps[`${report.report_id}:${m.id}`])) ? true : (report.maps.some((m) => enabledMaps[`${report.report_id}:${m.id}`]) ? "indeterminate" : false)}
                                                    onCheckedChange={(checked) =>
                                                        handleToggleLayer(report.report_id, -1, !!checked)
                                                    }
                                                />
                                                <TooltipProvider>
                                                    <Tooltip>
                                                        <TooltipTrigger className="font-bold no-wrap truncate ellipsis">
                                                            <span>{report.title}</span>
                                                        </TooltipTrigger>
                                                        <TooltipContent>
                                                            <p>{report.title}</p>
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </TooltipProvider>

                                            </div>
                                            <div className="flex items-center space-x-2 mt-1">
                                                <span className="text-sm text-gray-500">Opacity</span>
                                                <Slider
                                                    min={0}
                                                    max={1}
                                                    step={0.05}
                                                    value={[reportOpacity[report.report_id] ?? 1]}
                                                    onValueChange={(val) =>
                                                        handleChangeOpacity(report.report_id, val[0])
                                                    }
                                                    disabled={!enabledMaps[`${report.report_id}:${report.maps[0]?.id}`]}
                                                />
                                            </div>
                                            {report.maps.map((mapItem) => {
                                                const key = `${report.report_id}:${mapItem.id}`;
                                                const reportActive = report.maps.some((m) => enabledMaps[`${report.report_id}:${m.id}`]);
                                                return (
                                                    <div key={key} className="mt-2 pl-2">
                                                        <div className="flex items-center space-x-2">
                                                            <Checkbox
                                                                checked={enabledMaps[key]}
                                                                onCheckedChange={(checked) =>
                                                                    handleToggleLayer(report.report_id, mapItem.id, !!checked)
                                                                }
                                                            />
                                                            <TooltipProvider>
                                                                <Tooltip>
                                                                    <TooltipTrigger className={`font-bold no-wrap truncate ellipsis ${reportActive ? '' : 'text-gray-400'}`}>
                                                                        <span>{mapItem.name || `Map ${mapItem.id}`}</span>
                                                                    </TooltipTrigger>
                                                                    <TooltipContent>
                                                                        <p>{mapItem.name || `Map ${mapItem.id}`}</p>
                                                                    </TooltipContent>
                                                                </Tooltip>
                                                            </TooltipProvider>

                                                        </div>

                                                    </div>
                                                );
                                            })}

                                        </div>
                                    </>
                                )))}
                        </CardContent>
                    </Card>
                )}
            </div>)}

            {/* Reset View Button */}

            {/* Home Button */}
            <div
                style={{
                    position: "absolute",
                    top: "84px",
                    left: "12px",
                    zIndex: 1000,
                    padding: "4px",
                    borderRadius: "2px",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.8)",
                    cursor: "pointer"
                }}
                className="hover:bg-gray-100 bg-white transition-colors duration-200"
                title="Reset View"
                onClick={() => {
                    if (leafletMap) {
                        if (overallBounds) (leafletMap as any).fitBounds(overallBounds);
                        else (leafletMap as any).setView(center, 18.5);
                    }
                }}
            >
                <Home size={22} className="dark:text-black" />
            </div>
        </div>
    );
}




const CustomLayerControl: React.FC = ({ children,
    ...props }) => {
    const map = useMap();

    useEffect(() => {
        const controlContainer = map
            .getContainer()
            .querySelector('.leaflet-control-layers-toggle');

        if (controlContainer) {
            controlContainer.style.backgroundImage = 'none';
            // controlContainer.style.width = '';
            // controlContainer.style.height = '';
            controlContainer.innerHTML = ''; // Clear default
            // Optionally: Append a React root or directly inject your icon
            const root = createRoot(controlContainer);
            root.render(
                <div className="flex items-center justify-center w-full h-full">
                    <MapIcon className="w-7 h-7 text-gray-700" aria-hidden="true" />
                </div>
            );
        }
    }, [map]);

    return <LayersControl {...props}>{children}</LayersControl>;
};

