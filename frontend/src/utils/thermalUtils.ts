/**
 * Thermal image processing utilities
 * Handles matrix normalization and colormap rendering for thermal imagery
 */

export type ColorMapName =
    | "whiteHot"
    | "blackHot"
    | "ironbow"
    | "ironRed"
    | "rainbow"
    | "rainbowIsh"
    | "minmax"
    | "whspecial";

/**
 * Normalize a thermal matrix to 0-255 range based on min/max temperature bounds
 */
export function normalizeMatrix(
    matrix: number[][],
    minTemp: number,
    maxTemp: number
): number[][] {
    const range = maxTemp - minTemp || 1;
    const factor = 255 / range;

    return matrix.map((row) =>
        row.map((value) => (value - minTemp) * factor)
    );
}

/**
 * HSL to RGB conversion helper used by several color maps
 */
function hue2rgb(p: number, q: number, t: number): number {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
}

/**
 * Get a color mapping function for the specified colormap name
 * Each function takes a grayscale value (0-255) and returns [r, g, b]
 */
export function getColorMapFunction(
    colorMap: ColorMapName
): (gray: number) => number[] {
    switch (colorMap) {
        case "blackHot":
            return (gray) => [255 - gray, 255 - gray, 255 - gray];

        case "ironbow":
            return (gray) => [
                gray,
                (1 / 256) * gray ** 2,
                256 * (Math.sin(3 * (gray / 256 - 1 / 6) * Math.PI) + 1),
            ];

        case "ironRed":
            return (gray) => {
                let h = gray / 256 / 1.25 + 0.55;
                if (h > 1) h -= 1;
                const s = 1.0;
                const l = gray / 256;

                const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
                const p = 2 * l - q;

                const r = hue2rgb(p, q, h + 1 / 3);
                const g = hue2rgb(p, q, h);
                const b = hue2rgb(p, q, h - 1 / 3);
                return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
            };

        case "rainbowIsh":
            return (gray) => {
                gray = gray < 0 ? 0 : gray > 255 ? 255 : gray;
                return [
                    128 * (Math.sin((gray / 256 - 1 / 2) * Math.PI) + 1),
                    128 * (Math.sin((gray / 256) * Math.PI) + 1),
                    128 * (Math.sin((gray / 256 + 1 / 2) * Math.PI) + 1),
                ];
            };

        case "rainbow":
            return (gray) => {
                gray = gray < 0 ? 0 : gray > 255 ? 255 : gray;
                gray /= 256;
                const l = gray < 0.1 ? 0.25 + gray * 2.5 : 0.5;
                const s = 1.0;
                const h = 1 - gray;

                const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
                const p = 2 * l - q;

                const r = hue2rgb(p, q, h + 1 / 3);
                const g = hue2rgb(p, q, h);
                const b = hue2rgb(p, q, h - 1 / 3);
                return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
            };

        case "whspecial":
            return (gray) => [
                gray * 2.25,
                gray < 100
                    ? 90 - gray * 2.25
                    : gray < 200
                      ? gray * 2 - 200
                      : gray,
                gray < 100
                    ? 90 - gray * 1.75
                    : gray < 200
                      ? gray * 2 - 200
                      : gray,
            ];

        case "minmax":
            return (gray) => {
                gray = gray < 0 ? 0 : gray > 255 ? 255 : gray;
                gray /= 256;
                if (gray > 0.93) {
                    return [
                        255 * (gray - 0.8) * 7,
                        35 * (gray - 0.92) * 10 * 5,
                        20 * (gray - 0.92) * 10 * 5,
                    ];
                } else if (gray < 0.05) {
                    const c = 1.0 - gray * 10;
                    return [60 * 2 * c, 100 * 2 * c, 255];
                }
                return [255 * gray * 0.2, 255 * gray * 0.2, 255 * gray * 0.2];
            };

        case "whiteHot":
        default:
            return (gray) => [gray, gray, gray];
    }
}

/**
 * Convert a thermal matrix to an HTMLImageElement with the specified colormap applied
 */
export function matrixToCanvasImage(
    matrix: number[][],
    minTemp: number,
    maxTemp: number,
    colorMap: ColorMapName
): Promise<HTMLImageElement> {
    const normalized = normalizeMatrix(matrix, minTemp, maxTemp);
    const canvas = document.createElement("canvas");
    canvas.width = matrix[0].length;
    canvas.height = matrix.length;
    const ctx = canvas.getContext("2d");

    if (!ctx) throw new Error("2D context not available");

    const imageData = ctx.createImageData(canvas.width, canvas.height);
    const calcColors = getColorMapFunction(colorMap);

    for (let y = 0; y < canvas.height; y++) {
        for (let x = 0; x < canvas.width; x++) {
            const index = (y * canvas.width + x) * 4;
            const gray = normalized[y][x];
            const [r, g, b] = calcColors(gray);
            imageData.data[index] = r;
            imageData.data[index + 1] = g;
            imageData.data[index + 2] = b;
            // Alpha: reduce opacity for out-of-range values
            const alpha =
                gray > 255
                    ? Math.round(0.3 * 255)
                    : gray < 0.0
                      ? Math.round(0.3 * 255)
                      : 255;
            imageData.data[index + 3] = alpha;
        }
    }

    ctx.putImageData(imageData, 0, 0);

    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.src = canvas.toDataURL();
    });
}
