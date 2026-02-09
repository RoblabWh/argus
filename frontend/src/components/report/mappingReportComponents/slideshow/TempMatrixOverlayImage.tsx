import { useState, useEffect } from "react";
import { Image as KonvaImage } from "react-konva";
import { matrixToCanvasImage, type ColorMapName } from "@/utils/thermalUtils";

export interface TempMatrixOverlayImageProps {
    matrix: number[][];
    width: number;
    height: number;
    minTemp: number;
    maxTemp: number;
    y?: number;
    opacity?: number;
    scale?: { x: number; y: number };
    colorMap?: ColorMapName;
}

export function TempMatrixOverlayImage({
    matrix,
    width,
    height,
    minTemp = 20.0,
    maxTemp = 100.0,
    opacity = 1.0,
    colorMap = "whiteHot",
}: TempMatrixOverlayImageProps) {
    const [image, setImage] = useState<HTMLImageElement | null>(null);

    useEffect(() => {
        matrixToCanvasImage(matrix, minTemp, maxTemp, colorMap).then(setImage);
    }, [matrix, matrix[0].length, matrix.length, minTemp, maxTemp, colorMap]);

    if (!image) return null;

    const scaleX = width / matrix[0].length;
    const scaleY = height / matrix.length;

    return (
        <KonvaImage
            image={image}
            opacity={opacity}
            scale={{ x: scaleX, y: scaleY }}
        />
    );
}
