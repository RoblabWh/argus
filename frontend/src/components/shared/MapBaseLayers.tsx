import { LayersControl, TileLayer } from "react-leaflet";
import { useTheme } from "@/components/ui/theme-provider";

const { BaseLayer } = LayersControl;

const MAPBOX_TOKEN =
    "pk.eyJ1Ijoicm9ibGFidXNlcndocyIsImEiOiJja3VjaXF3d2MxMTN5Mm9tdmQzaGphdGU3In0.BhKF_054bVOPcviIq2yIKg";

/**
 * The four base layers shared by every Leaflet map in the app.
 *
 * Render inside a <LayersControl> — react-leaflet's BaseLayer registers itself through
 * context, so it does not have to be a direct child of the control.
 */
export function MapBaseLayers() {
    const { theme } = useTheme();
    const current = theme === "system"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light"
        : theme;

    return (
        <>
            <BaseLayer checked name="Mapbox Streets">
                <TileLayer
                    id={current === "dark" ? "mapbox/dark-v11" : "mapbox/streets-v11"}
                    attribution="&copy; Mapbox contributors"
                    url={`https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`}
                    maxZoom={23}
                />
            </BaseLayer>

            <BaseLayer name="OpenStreetMap">
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

            <BaseLayer name="Mapbox Satellite">
                <TileLayer
                    id="mapbox/satellite-v9"
                    attribution="&copy; Mapbox contributors"
                    url={`https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`}
                    maxZoom={23}
                />
            </BaseLayer>
        </>
    );
}
