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
import { Button } from "@/components/ui/button";
import { Home, Map } from "lucide-react";
import type { ReportSummary } from "@/types/report";
import "leaflet/dist/leaflet.css";

const { BaseLayer } = LayersControl;

export function GroupMapTab({
    summaryReports
}: {
    summaryReports: ReportSummary[];
}) {
    const api_url = getApiUrl();
    const [isLayerControlExpanded, setIsLayerControlExpanded] = useState(false);
    const hideTimer = useRef<NodeJS.Timeout | null>(null);
    const [leafletMap, setLeafletMap] = useState<LeafletMap | null>(null);
    const { theme } = useTheme();

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

    const [enabledMaps, setEnabledMaps] = useState<Record<string, boolean>>(
        () =>
            Object.fromEntries(
                summaryReports.flatMap((r) =>
                    (r.maps || []).map((m) => [`${r.report_id}:${m.id}`, true])
                )
            )
    );

    const overallBounds = useMemo(() => {
        const allMaps = summaryReports.flatMap((r) => r.maps || []);
        if (!allMaps.length) return null;

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
    }, [summaryReports]);

    const center = useMemo(() => {
        if (!overallBounds) return [51.574, 7.027] as [number, number];
        const [[latMin, lonMin], [latMax, lonMax]] = overallBounds;
        return [(latMin + latMax) / 2, (lonMin + lonMax) / 2] as [number, number];
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
        setEnabledMaps((prev) => ({
            ...prev,
            [`${reportId}:${mapId}`]: visible
        }));
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
                <LayersControl position="topright">
                    <BaseLayer checked name="OpenStreetMap">
                        <TileLayer
                            attribution="&copy; OpenStreetMap contributors"
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                            maxZoom={22}
                        />
                    </BaseLayer>
                    <BaseLayer name="Esri Satellite">
                        <TileLayer
                            attribution="Tiles © Esri"
                            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                            maxZoom={21}
                        />
                    </BaseLayer>
                </LayersControl>

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
            <div className="absolute top-16 right-4 z-1001"
                onMouseEnter={showPanel}
                onMouseLeave={hidePanel}>
                {!isLayerControlExpanded ? (
                    <div className="flex items-center bg-white p-2 rounded shadow hover:bg-gray-100 transition-colors">
                        <Map className="h-6 w-6" />
                    </div>
                ) : (
                    <Card className="w-72 max-h-[80vh] overflow-y-auto">
                        <CardHeader>
                            <CardTitle>Layer Control</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {summaryReports.map((report) => (
                                <div key={report.report_id} className="mb-4">
                                    <div className="font-bold">{report.title}</div>
                                    {report.maps.map((mapItem) => {
                                        const key = `${report.report_id}:${mapItem.id}`;
                                        return (
                                            <div key={key} className="mt-2">
                                                <div className="flex items-center space-x-2">
                                                    <Checkbox
                                                        checked={enabledMaps[key]}
                                                        onCheckedChange={(checked) =>
                                                            handleToggleLayer(report.report_id, mapItem.id, !!checked)
                                                        }
                                                    />
                                                    <span>{mapItem.name || `Map ${mapItem.id}`}</span>
                                                </div>

                                            </div>
                                        );
                                    })}
                                    <Slider
                                        min={0}
                                        max={1}
                                        step={0.05}
                                        value={[reportOpacity[report.report_id] ?? 1]}
                                        onValueChange={(val) =>
                                            handleChangeOpacity(report.report_id, val[0])
                                        }
                                    />
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                )}
            </div>

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
