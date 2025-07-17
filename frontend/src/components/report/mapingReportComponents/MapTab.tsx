import type { Report } from "@/types/report";
import { getApiUrl } from "@/api";
import { MapContainer, TileLayer, LayersControl } from 'react-leaflet';
import { useTheme } from "@/components/ui/theme-provider";
import 'leaflet/dist/leaflet.css';

const { BaseLayer } = LayersControl;

interface Props {
    report: Report;
}

export function MapTab({ report }: Props) {
    const api_url = getApiUrl();
    const { theme } = useTheme();
    const current = theme === "system"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light"
        : theme;    //Check if report has maps, If not show overlay over map (that can be closed by clicking, but since no gps data is available the map will start ata default location (in fututre editable in settins))

    return (
        <MapContainer center={[51.574, 7.027]} zoom={18} style={{ zIndex: 0, flex: 1, height: '100%' }}>
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



            </LayersControl>
        </MapContainer>
    );
}