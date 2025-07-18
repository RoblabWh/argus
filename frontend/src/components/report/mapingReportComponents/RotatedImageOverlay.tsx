import { useMap, useMapEvent } from "react-leaflet";
import { useLeafletContext } from '@react-leaflet/core';

import { useEffect, useRef } from "react";
import L from "leaflet";

type Props = {
    url: string;
    corners: [[number, number], [number, number], [number, number]]; // topLeft, topRight, bottomLeft
    opacity?: number;
};

export function RotatedImageOverlay({ url, corners, opacity = 1.0 }: Props) {
    const context = useLeafletContext();
    const overlayRef = useRef<L.ImageOverlay | null>(null);
    
    

    useEffect(() => {
        const overlay = new L.ImageOverlay.Rotated(url, corners[0], corners[1], corners[2], {
            opacity,
        });

       context.layerContainer.addLayer(overlay);
        overlayRef.current = overlay;


        return () => {
            context.layerContainer.removeLayer(overlayRef.current);
        };
    }, [context, url, corners, opacity]);

    return null;
}
