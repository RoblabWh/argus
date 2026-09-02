import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, LayersControl, Marker, useMap, useMapEvents } from "react-leaflet";
import type { Map as LeafletMap } from "leaflet";
import { Loader2, MapPin, Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MapBaseLayers } from "@/components/shared/MapBaseLayers";
import { useGeocodeSearch } from "@/hooks/useGeocodeSearch";
import type { GeocodeResult } from "@/api";

export interface Coordinate {
    lat: number;
    lon: number;
}

interface Props {
    value: Coordinate | null;
    onChange: (c: Coordinate) => void;
    /** Where to open the map when nothing has been picked yet. */
    defaultCenter?: Coordinate;
    /** Re-runs Leaflet's size calculation — pass the dialog's open state. */
    visible?: boolean;
    className?: string;
}

// Wide view over Germany — the DRZ operating area — when we have nothing better.
const FALLBACK_CENTER: Coordinate = { lat: 51.16, lon: 10.45 };
const FALLBACK_ZOOM = 5;
const PICKED_ZOOM = 17;

/** Sets the coordinate wherever the user clicks. */
function ClickHandler({ onChange }: { onChange: (c: Coordinate) => void }) {
    useMapEvents({
        click: (e) => onChange({ lat: e.latlng.lat, lon: e.latlng.lng }),
    });
    return null;
}

/**
 * Leaflet measures the container on mount. Inside a dialog that is still animating,
 * that measurement is wrong and the map renders as a grey sliver, so recompute it
 * once the dialog is actually visible.
 */
function InvalidateOnShow({ visible }: { visible?: boolean }) {
    const map = useMap();
    useEffect(() => {
        if (visible === false) return;
        const t = setTimeout(() => map.invalidateSize(), 150);
        return () => clearTimeout(t);
    }, [map, visible]);
    return null;
}

/** Flies to a coordinate that was set from outside the map (search hit, manual input). */
function FlyTo({ target }: { target: Coordinate | null }) {
    const map = useMap();
    useEffect(() => {
        if (target) map.flyTo([target.lat, target.lon], Math.max(map.getZoom(), PICKED_ZOOM));
    }, [map, target]);
    return null;
}

/**
 * Pick a GPS coordinate on a map, by address search, by clicking, or by typing it in.
 *
 * Kept free of any report-specific knowledge so it can also serve mapping-report images
 * that have no EXIF GPS.
 */
export function CoordinatePickerMap({ value, onChange, defaultCenter, visible, className }: Props) {
    const [term, setTerm] = useState("");
    const [flyTarget, setFlyTarget] = useState<Coordinate | null>(null);
    const [latText, setLatText] = useState(value ? String(value.lat) : "");
    const [lonText, setLonText] = useState(value ? String(value.lon) : "");
    const mapRef = useRef<LeafletMap | null>(null);

    const { data: results, isFetching } = useGeocodeSearch(term);

    // Only used for the initial render — afterwards the map keeps its own view.
    const initial = useMemo(
        () => value ?? defaultCenter ?? FALLBACK_CENTER,
        // eslint-disable-next-line react-hooks/exhaustive-deps
        []
    );
    const initialZoom = value || defaultCenter ? PICKED_ZOOM : FALLBACK_ZOOM;

    // Keep the text inputs in sync when the coordinate changes from the map
    useEffect(() => {
        if (value) {
            setLatText(value.lat.toFixed(6));
            setLonText(value.lon.toFixed(6));
        }
    }, [value]);

    const pick = (c: Coordinate, fly = false) => {
        onChange(c);
        if (fly) setFlyTarget(c);
    };

    const commitManual = () => {
        const lat = parseFloat(latText.replace(",", "."));
        const lon = parseFloat(lonText.replace(",", "."));
        if (Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180) {
            pick({ lat, lon }, true);
        }
    };

    const selectResult = (r: GeocodeResult) => {
        setTerm("");
        pick({ lat: r.lat, lon: r.lon }, true);
    };

    return (
        <div className={className}>
            {/* Address search */}
            <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                    value={term}
                    onChange={(e) => setTerm(e.target.value)}
                    placeholder="Search for an address or place…"
                    className="pl-8"
                />
                {isFetching && (
                    <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 size-4 animate-spin text-muted-foreground" />
                )}
                {term.trim().length >= 3 && results && (
                    <div
                        // z-1100 keeps the results above Leaflet's own controls, which sit at 1000
                        className="absolute z-[1100] mt-1 w-full max-h-40 overflow-y-auto rounded-md border bg-popover shadow-md"
                    >
                        {results.length === 0 ? (
                            <p className="px-3 py-2 text-xs text-muted-foreground">
                                {isFetching ? "Searching…" : "No matches — pick the spot on the map instead."}
                            </p>
                        ) : (
                            results.map((r) => (
                                <button
                                    key={`${r.lat},${r.lon},${r.display_name}`}
                                    type="button"
                                    onClick={() => selectResult(r)}
                                    className="block w-full text-left px-3 py-2 text-xs hover:bg-accent"
                                >
                                    {r.display_name}
                                </button>
                            ))
                        )}
                    </div>
                )}
            </div>

            {/* Map */}
            <div className="mt-2 h-64 w-full overflow-hidden rounded-md border">
                <MapContainer
                    center={[initial.lat, initial.lon]}
                    zoom={initialZoom}
                    style={{ height: "100%", width: "100%" }}
                    ref={mapRef}
                >
                    <LayersControl position="topright">
                        <MapBaseLayers />
                    </LayersControl>
                    <ClickHandler onChange={(c) => pick(c)} />
                    <InvalidateOnShow visible={visible} />
                    <FlyTo target={flyTarget} />
                    {value && (
                        <Marker
                            position={[value.lat, value.lon]}
                            draggable
                            eventHandlers={{
                                dragend: (e) => {
                                    const { lat, lng } = e.target.getLatLng();
                                    pick({ lat, lon: lng });
                                },
                            }}
                        />
                    )}
                </MapContainer>
            </div>

            <p className="mt-1.5 flex items-center gap-1 text-xs text-muted-foreground">
                <MapPin className="size-3" />
                Click the map or drag the marker to set the position.
            </p>

            {/* Manual entry */}
            <div className="mt-2 grid grid-cols-2 gap-2">
                <div className="space-y-1">
                    <Label className="text-xs">Latitude</Label>
                    <Input
                        value={latText}
                        onChange={(e) => setLatText(e.target.value)}
                        onBlur={commitManual}
                        onKeyDown={(e) => e.key === "Enter" && commitManual()}
                        placeholder="51.518315"
                        inputMode="decimal"
                    />
                </div>
                <div className="space-y-1">
                    <Label className="text-xs">Longitude</Label>
                    <Input
                        value={lonText}
                        onChange={(e) => setLonText(e.target.value)}
                        onBlur={commitManual}
                        onKeyDown={(e) => e.key === "Enter" && commitManual()}
                        placeholder="7.460135"
                        inputMode="decimal"
                    />
                </div>
            </div>
        </div>
    );
}
