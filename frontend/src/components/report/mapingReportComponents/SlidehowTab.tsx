import React, { useRef, useEffect, useState } from "react";
import { Stage, Layer, Image as KonvaImage, Rect } from "react-konva";
import type { Image } from "@/types/image";
import { ThermalSettingsPopup } from "./thermalSettingsPopup";
import useImage from "use-image";
import { useThermalMatrix } from "@/hooks/useThermalMatrix";
import { getApiUrl } from "@/api";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { ChevronLeft, ChevronRight, Thermometer, Scan, Locate, MousePointer2, Wand } from "lucide-react";
import { useAspectRatio } from "@/hooks/useAspectRatio";
import { set } from "date-fns";
import { m } from "motion/react";




interface SlideshowTabProps {
    selectedImage: Image | null;
    images: Image[];
    nextImage: () => void;
    previousImage: () => void;
}

export const SlideshowTab: React.FC<SlideshowTabProps> = ({
    selectedImage,
    images,
    nextImage,
    previousImage,
}) => {
    const apiUrl = getApiUrl();
    const containerRef = useRef<HTMLDivElement>(null);
    const stageRef = useRef<any>(null);

    const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
    const [imageUrl, setImageUrl] = useState<string | null>(null);
    const [image] = useImage(imageUrl || "");

    const [scale, setScale] = useState(1);
    const [minScale, setMinScale] = useState(1);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const fallbackScale = 0.475; // Default scale for thermal images


    const [backgroundImageUrl, setBackgroundImageUrl] = useState<string | null>(null);
    const [backgroundImageName, setBackgroundImageName] = useState<string | null>(null);
    const [backgroundImage] = useImage(backgroundImageUrl || "");
    const [opacity, setOpacity] = useState(1);

    const [showOpacityPanel, setShowOpacityPanel] = useState(false);

    const [tempMode, setTempMode] = useState(false);
    const [tempMatrix, setTempMatrix] = useState<number[][] | null>(null);
    const [minmaxTemp, setMinMaxTemp] = useState<{ min: number; max: number }>({ min: 20, max: 100 });

    const [thermalSettingsPopupOpen, setThermalSettingsPopupOpen] = useState(false);
    const [thermalSettings, setThermalSettings] = useState({
        probeRadius: 4,
        recolor: true,
        autoTempLimits: true,
        minTemp: 20,
        maxTemp: 100,
        colorMap: "whiteHot",
    });

    const { data, isLoading, error, refetch } = useThermalMatrix(selectedImage?.id, selectedImage?.thermal);

    const [probeResult, setProbeResult] = useState<{
        x: number;
        y: number;
        probeMessage: string;
    } | null>(null);


    useEffect(() => {
        if (data && selectedImage?.id === data.image_id) {
            setTempMatrix(data.matrix);
            let minTemp = data.min_temp || 20.0;
            let maxTemp = data.max_temp || 100.0;
            console.log("Thermal matrix loaded for image:", selectedImage.id, "Min Temp:", minTemp, "Max Temp:", maxTemp);
            // Optionally, you can set min/max
            setMinMaxTemp({ min: minTemp, max: maxTemp });
        } else {
            setTempMatrix(null);
        }
    }, [data, selectedImage?.id]);


    useEffect(() => {
        if (!selectedImage) return;
        if (tempMode && selectedImage.thermal) {
            if (!data) return;

            setTempMatrix(data.matrix);
            let minTemp = data.min_temp || 20.0;
            let maxTemp = data.max_temp || 100.0;
            console.log("Thermal matrix loaded for image:", selectedImage.id, "Min Temp:", minTemp, "Max Temp:", maxTemp);
            // Optionally, you can set min/max
            setMinMaxTemp({ min: minTemp, max: maxTemp });
        }
    }, [tempMode]);


    useEffect(() => {
        if (!containerRef.current) return;

        const observeResize = () => {
            const el = containerRef.current!;
            const observer = new ResizeObserver(([entry]) => {
                const { width, height } = entry.contentRect;
                // leave some space for controls
                const adjustedHeight = height - 90; // tweak as needed
                const size = Math.min(width, adjustedHeight); // keep square canvas
                setContainerSize({ width: width, height: size });
            });

            observer.observe(el);
            return () => observer.disconnect();
        };

        return observeResize();
    }, []);


    // When a new image is selected, update image URL and reset scale/position
    useEffect(() => {
        // if (selectedImage) {
        //     setImageUrl(`${apiUrl}/${selectedImage.url}`);
        // }
        if (!selectedImage) return;

        setProbeResult(null); // reset probe result on new image selection
        setImageUrl(`${apiUrl}/${selectedImage.url}`);


        if (selectedImage.thermal && selectedImage.thermal_data?.counterpart_id) {
            const rgbImage = images.find(img => img.id === selectedImage.thermal_data?.counterpart_id);
            if (rgbImage) {
                console.log("Setting background image for thermal counterpart:", rgbImage.filename);
                setBackgroundImageUrl(`${apiUrl}/${rgbImage.url}`);
                setBackgroundImageName(rgbImage.filename);
            } else {
                setBackgroundImageUrl(null); // fallback
                setBackgroundImageName(null);
            }
            //refetch(); // refetch thermal matrix for new image
            if (data && selectedImage?.id === data.image_id && tempMode) {
                setTempMatrix(data.matrix);
                let minTemp = data.min_temp || 20.0;
                let maxTemp = data.max_temp || 100.0;
                console.log("Thermal matrix loaded for image:", selectedImage.id, "Min Temp:", minTemp, "Max Temp:", maxTemp);
                // Optionally, you can set min/max
                setMinMaxTemp({ min: minTemp, max: maxTemp });
            } else {
                setTempMatrix(null);
            }
        } else {
            setTempMode(false); // reset temp mode
            setBackgroundImageUrl(null);
            setBackgroundImageName(null);
            setOpacity(1.0);
        }
    }, [selectedImage, images]);




    // Fit and center image when loaded or canvas size changes
    useEffect(() => {
        if (!image || !containerSize.width || !containerSize.height) return;
        resetView();
    }, [image, containerSize]);


    const resetView = () => {
        if (!image || !containerSize.width || !containerSize.height) return;

        const scaleX = containerSize.width / image.width;
        const scaleY = containerSize.height / image.height;
        const fitScale = Math.min(scaleX, scaleY);

        const offsetX = (containerSize.width - image.width * fitScale) / 2;
        const offsetY = (containerSize.height - image.height * fitScale) / 2;

        setScale(fitScale);
        setMinScale(fitScale);
        setPosition({ x: offsetX, y: offsetY });
    };


    const handleSettingsSave = (settings: any) => {
        if (!settings) return;
        setThermalSettings(settings);
    };

    // Handle zoom (wheel)
    const handleWheel = (e: any) => {
        e.evt.preventDefault();
        const scaleBy = 1.05;
        const stage = stageRef.current;
        const oldScale = stage.scaleX();

        const pointer = stage.getPointerPosition();
        if (!pointer || !image) return;

        const mousePointTo = {
            x: (pointer.x - stage.x()) / oldScale,
            y: (pointer.y - stage.y()) / oldScale,
        };

        // Compute new scale (clamped)
        let newScale = e.evt.deltaY > 0 ? oldScale / scaleBy : oldScale * scaleBy;
        newScale = Math.max(minScale, newScale);

        // Compute new position so zoom focuses around mouse
        let newX = pointer.x - mousePointTo.x * newScale;
        let newY = pointer.y - mousePointTo.y * newScale;

        // Calculate new scaled image size
        const scaledWidth = image.width * newScale;
        const scaledHeight = image.height * newScale;

        // Clamp new position to keep image inside canvas
        const maxX = 0;
        const minX = containerSize.width - scaledWidth;
        const maxY = 0;
        const minY = containerSize.height - scaledHeight;

        if (scaledWidth <= containerSize.width) {
            newX = (containerSize.width - scaledWidth) / 2;
        } else {
            newX = Math.min(maxX, Math.max(minX, newX));
        }

        if (scaledHeight <= containerSize.height) {
            newY = (containerSize.height - scaledHeight) / 2;
        } else {
            newY = Math.min(maxY, Math.max(minY, newY));
        }

        setScale(newScale);
        setPosition({ x: newX, y: newY });
        setProbeResult(null); // reset probe result on zoom
    };





    // Clamp dragging so image stays inside canvas
    const handleDragMove = (e: any) => {
        if (!image || !containerSize.width || !containerSize.height) return;

        const node = e.target;
        const scaledWidth = image.width * scale;
        const scaledHeight = image.height * scale;

        const maxX = 0;
        const minX = containerSize.width - scaledWidth;
        const maxY = 0;
        const minY = containerSize.height - scaledHeight;

        // Clamp values (only if image is larger than canvas in that axis)
        const clampedX = scaledWidth > containerSize.width
            ? Math.min(maxX, Math.max(minX, node.x()))
            : (containerSize.width - scaledWidth) / 2;

        const clampedY = scaledHeight > containerSize.height
            ? Math.min(maxY, Math.max(minY, node.y()))
            : (containerSize.height - scaledHeight) / 2;

        node.position({ x: clampedX, y: clampedY });
        setPosition({ x: clampedX, y: clampedY });
        setProbeResult(null); // reset probe result on drag
    };


    const handleMouseClick = (e: any) => {

        var stage = e.currentTarget;
        const stageScale = stage.scaleX();
        const pointer = stage.getPointerPosition();
        if (!pointer || !image) return;

        // (Pointer position + image position) * 1/scale
        const posiOnImageX = (pointer.x - position.x) * (1 / stageScale);
        const posiOnImageY = (pointer.y - position.y) * (1 / stageScale);

        const imageWidth = image ? image.width : 0;
        const imageHeight = image ? image.height : 0;

        if (posiOnImageX < 0 || posiOnImageX > imageWidth || posiOnImageY < 0 || posiOnImageY > imageHeight) return;

        if (tempMode) {//&& tempMatrix) {
            const ix = Math.floor(posiOnImageX / 2);
            const iy = Math.floor(posiOnImageY / 2);



            // if (!tempMatrix || ix < 0 || ix >= tempMatrix.length || iy < 0 || iy >= tempMatrix[ix].length) {
            //     setProbeResult(null);
            //     return;
            // }
            let probeMessage = "";
            if (!tempMatrix) {
                probeMessage = "No reading available";
            } else {

                const sampleRadius = thermalSettings.probeRadius; // sample radius of 4 pixels
                const minX = Math.max(0, ix - sampleRadius);
                const maxX = Math.min(tempMatrix[0].length - 1, ix + sampleRadius);
                const minY = Math.max(0, iy - sampleRadius);
                const maxY = Math.min(tempMatrix.length - 1, iy + sampleRadius);

                const roi = tempMatrix.slice(minY, maxY + 1).map(row => row.slice(minX, maxX + 1));

                let maxTemp = Math.round(10 * Math.max(...roi.flat()) / 10);
                let minTemp = Math.round(10 * Math.min(...roi.flat()) / 10);

                probeMessage = `Max: ${maxTemp}°C, Min: ${minTemp}°C`;

                console.log("Probe clicked at:", posiOnImageX, posiOnImageY, "Matrix size:", tempMatrix.length, "x", tempMatrix[0].length, "trying to get:", ix, iy);
                // const temperature = tempMatrix[iy]?.[ix];
            }

            setProbeResult({
                x: pointer.x,
                y: pointer.y,
                probeMessage: probeMessage,
            });

        }


    }

    useEffect(() => {
        if (!probeResult) return;
        const timer = setTimeout(() => setProbeResult(null), 3000);
        return () => clearTimeout(timer);
    }, [probeResult]);


    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "ArrowRight") nextImage();
            if (e.key === "ArrowLeft") previousImage();
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [nextImage, previousImage]);


    return (
        <div className="flex flex-col h-full w-full overflow-hidden justify-start" ref={containerRef}>
            <div className="bg-white dark:bg-gray-800">
                {selectedImage ? (
                    <>
                        <Stage
                            ref={stageRef}
                            width={containerSize.width}
                            height={containerSize.height}
                            scaleX={scale}
                            scaleY={scale}
                            x={position.x}
                            y={position.y}
                            onWheel={handleWheel}
                            draggable
                            onDragMove={handleDragMove}
                            onMouseUp={handleMouseClick}
                        >
                            <Layer>
                                {/* Background RGB image (if exists) */}
                                {backgroundImage && selectedImage?.thermal && selectedImage.thermal_data?.counterpart_scale && (
                                    <KonvaImage
                                        image={backgroundImage}
                                        scale={{
                                            x: image ? selectedImage.thermal_data.counterpart_scale : fallbackScale,
                                            y: image ? selectedImage.thermal_data.counterpart_scale : fallbackScale,
                                        }}
                                        x={image ? -((backgroundImage.width * selectedImage.thermal_data.counterpart_scale - image.width)) / 2 : 0}
                                        y={image ? -((backgroundImage.height * selectedImage.thermal_data.counterpart_scale - image.height)) / 2 : 0}
                                        opacity={1}
                                    />
                                )}

                                {/* Foreground thermal image */}
                                {(image && (!tempMode || (!tempMatrix && tempMode)) || (!thermalSettings.recolor)) && (
                                    <KonvaImage
                                        image={image}
                                        opacity={opacity}
                                    />
                                )}


                                {(tempMatrix && tempMode && thermalSettings.recolor) && (
                                    <MatrixOverlayImage
                                        matrix={tempMatrix}
                                        width={image?.width || containerSize.width}
                                        height={image?.height || containerSize.height}
                                        minTemp={thermalSettings.autoTempLimits ? minmaxTemp.min : thermalSettings.minTemp}
                                        maxTemp={thermalSettings.autoTempLimits ? minmaxTemp.max : thermalSettings.maxTemp}
                                        colorMap={thermalSettings.colorMap}
                                        opacity={opacity} // or whatever makes sense
                                    />
                                )}

                                {/* {probeResult && (
                                    <Rect
                                        x={probeResult.x - 10}
                                        y={probeResult.y - 10}
                                        width={8}
                                        height={8}
                                        stroke="red"
                                        strokeWidth={2}
                                        fill="transparent"
                                    />
                                )} */}

                            </Layer>
                        </Stage>

                        {probeResult && (
                            <>
                                <Scan className="absolute z-50 stroke-3 w-6 h-6"
                                    style={{
                                        left: probeResult.x - 12,
                                        top: probeResult.y - 12,
                                        pointerEvents: "none",
                                    }}
                                />
                                <Badge
                                    variant="default"
                                    className="absolute z-60 font-semibold text-md"
                                    style={{
                                        left: probeResult.x - 84,
                                        top: probeResult.y + 16,
                                    }}

                                >
                                    {probeResult.probeMessage}
                                </Badge>
                            </>
                        )}
                        {selectedImage?.thermal && selectedImage.thermal_data?.counterpart_id && (
                            <div
                                className={`absolute  z-50 left-1/2 -translate-x-1/2 transition-all duration-300 ${showOpacityPanel ? 'translate-y-[-120%]' : 'translate-y-[-24px]'} opacity-60 hover:opacity-100`}
                            >
                                <div className="flex flex-col items-center justify-center">
                                    {/* Toggle Button */}
                                    <button
                                        onClick={() => setShowOpacityPanel(!showOpacityPanel)}
                                        className={`w-8 ${showOpacityPanel ? 'h-5' : 'h-6'} bg-white dark:bg-gray-800  rounded-t-md flex items-center justify-center text-xs `}
                                    >
                                        {showOpacityPanel ? "▼" : "▲"}
                                    </button>
                                </div>
                                <div
                                    className={`flex flex-row bg-white dark:bg-gray-800 rounded-lg px-2 py-2 shadow-lg relative gap-2 h-10 w.full ${showOpacityPanel ? 'display-block' : 'hidden'} transition-opacity duration-300 `}
                                >
                                    <div className="flex flex-row items-center justify-center gap-2">
                                        {/* <Button variant="outline" onClick={() => console.log("Locate clicked")} className="w-8 h-8 p-0 m-0">
                                            <div className="p-0 m-0 w-full h-full flex items-center justify-center relative">
                                                <Locate className="size-8 stroke-1" />
                                                <Thermometer className="size4 absolute translate-y-[0%] translate-x-[0%] stroke-2" />
                                            </div>
                                        </Button> */}
                                        <Button
                                            variant={tempMode ? "active" : "default"}
                                            onClick={() => {
                                                setTempMode(!tempMode); // disable temp mode if no matrix
                                                if (tempMode) setProbeResult(null); // hide popup when disabling
                                            }}
                                            className={`w-7 h-7 p-2 m-0 hover:cursor-pointer`}
                                        >
                                            <div className="p-0 m-0 w-full h-full flex items-center justify-center relative">
                                                {/* <MousePointer2 className="size-4 stroke-2 translate-y-[30%]  translate-x-[30%]" /> */}
                                                <Wand className="size-5 stroke-2 translate-y-[5%]  translate-x-[15%]" />
                                                <Thermometer className="size-[48%] absolute translate-y-[-26%] translate-x-[-50%] stroke-2" />
                                            </div>
                                        </Button>
                                        <span className="text-xs whitespace-nowrap">Temp-Probe</span>
                                    </div>

                                    <Separator orientation="vertical" className="mx-2 bg-black dark:bg-white" />

                                    <div className="flex flex-row items-center justify-center w-full gap-2">

                                        <Slider
                                            defaultValue={[100]}
                                            max={100}
                                            min={0}
                                            step={1}
                                            onValueChange={([val]) => setOpacity(val / 100)}
                                            className="min-w-[100px] hover:cursor-pointer"
                                        />
                                        <p className="text-xs text-center mt-1 opacity-80 whitespace-nowrap">Thermal Opacity</p>
                                    </div>
                                </div>

                            </div>
                        )}
                    </>

                ) : (
                    <p>No image selected</p>
                )}
            </div>

            <div className="grid grid-cols-3 items-center justify-between mt-4 p-4 w-full bg-white dark:bg-gray-800">
                <Tooltip className="flex justify-start">
                    <TooltipTrigger className="flex justify-start">
                        <div className="text-sm text-muted-foreground whitespace-nowrap overflow-hidden text-ellipsis">
                            {selectedImage?.filename ?? ""} {backgroundImageName ? `(${backgroundImageName})` : ""}
                        </div>
                    </TooltipTrigger>
                    <TooltipContent>
                        <p>{selectedImage?.filename ?? ""} {backgroundImageName ? `(${backgroundImageName})` : ""}</p>
                    </TooltipContent>
                </Tooltip>

                <div className="flex items-center gap-4 w-full justify-center">
                    <Button variant="default" onClick={previousImage} className="aspect-square">
                        <ChevronLeft />
                    </Button>
                    <Button variant="default" onClick={nextImage} className="aspect-square">
                        <ChevronRight />
                    </Button>
                </div>

                <div className="flex items-center justify-end gap-2">
                    {selectedImage?.thermal && (
                    <Button
                        variant={tempMode ? "active" : "default"}
                        onClick={() => {
                            setTempMode(!tempMode); // disable temp mode if no matrix
                            if (tempMode) setProbeResult(null); // hide popup when disabling
                        }}
                        className={`aspect-square w-10 hover:cursor-pointer ${tempMode ? '' : ''}`}
                    >
                        <div className="aspect-square p-0 m-0 flex items-center justify-center relative">
                            {/* <MousePointer2 className="size-4 stroke-2 translate-y-[30%]  translate-x-[30%]" /> */}
                            <Wand className="size-5 stroke-2 translate-y-[5%]  translate-x-[15%]" />
                            <Thermometer className="size-[48%] absolute translate-y-[-26%] translate-x-[-50%] stroke-2" />
                        </div>
                    </Button> )}
                    {selectedImage?.thermal && (
                        <Button variant="outline" onClick={() => setThermalSettingsPopupOpen(true)}>
                            <Thermometer className="w-4 h-4 mr-2" />
                            Thermal Settings
                        </Button>
                    )}
                    <Button variant="outline" onClick={resetView}>
                        Reset View
                    </Button>
                </div>
            </div>
            <ThermalSettingsPopup
                open={thermalSettingsPopupOpen}
                onOpenChange={setThermalSettingsPopupOpen}
                settings={thermalSettings}
                onSave={handleSettingsSave}
            />
        </div>

    );
};



interface MatrixOverlayImageProps {
    matrix: number[][];
    width: number;
    height: number;
    minTemp: number;
    maxTemp: number;
    y?: number;
    opacity?: number;
    scale?: { x: number; y: number };
    colorMap?: string;
}

function normalizeMatrix(matrix: number[][], minTemp: number, maxTemp: number): number[][] {
    const min = minTemp;
    const max = maxTemp;
    const range = max - min || 1;

    let factor = 255 / range;
    return matrix.map(row =>
        row.map(value => Math.round(((value - min) * factor)))
    );
}

function matrixToCanvasImage(
    matrix: number[][],
    minTemp: number,
    maxTemp: number,
    colorMap: string
): Promise<HTMLImageElement> {
    const normalized = normalizeMatrix(matrix, minTemp, maxTemp);
    const canvas = document.createElement("canvas");
    canvas.width = matrix[0].length;
    canvas.height = matrix.length;
    const ctx = canvas.getContext("2d");

    if (!ctx) throw new Error("2D context not available");

    const imageData = ctx.createImageData(canvas.width, canvas.height);
    let calcColors: (gray: number) => number[];
    switch (colorMap) {

        case "blackHot":
            calcColors = (gray) => [255 - gray, 255 - gray, 255 - gray];
            break;
        case "ironbow":
            calcColors = (gray) => [
                gray,
                (1 / 256) * gray ** 2,
                256 * (Math.sin(3 * ((gray / 256) - 1 / 6) * Math.PI) + 1)
            ];
            break;
        case "rainbow":
            calcColors = (gray) => [
                256 * (Math.sin(3 * ((gray / 256) - 2 / 6) * Math.PI) + 1),
                256 * (Math.sin(3 * ((gray / 256)) * Math.PI) + 1),
                256 * (Math.sin(3 * ((gray / 256) + 1 / 6) * Math.PI) + 1),
            ];
            break;

        case "whspecial":
            calcColors = (gray) => [
                gray * 2.25,
                (gray < 100 ? 90 - gray * 2.25 : (gray < 200 ? gray * 2 - 200 : gray)),
                (gray < 100 ? 90 - gray * 1.75 : (gray < 200 ? gray * 2 - 200 : gray)),
            ];
            break;
        case "whiteHot":
        default:
            calcColors = (gray) => [gray, gray, gray];
            break;

    }

    for (let y = 0; y < canvas.height; y++) {
        for (let x = 0; x < canvas.width; x++) {
            const index = (y * canvas.width + x) * 4;
            const gray = normalized[y][x];
            const [r, g, b] = calcColors(gray);
            imageData.data[index] = r;
            imageData.data[index + 1] = g;
            imageData.data[index + 2] = b;
            imageData.data[index + 3] = 255;
        }
    }

    ctx.putImageData(imageData, 0, 0);

    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.src = canvas.toDataURL();
    });
}

const MatrixOverlayImage: React.FC<MatrixOverlayImageProps> = ({
    matrix,
    width,
    height,
    minTemp = 20.0,
    maxTemp = 100.0,
    opacity = 1.0,
    colorMap = "whiteHot",
}) => {
    const [image, setImage] = useState<HTMLImageElement | null>(null);

    useEffect(() => {
        matrixToCanvasImage(matrix, minTemp, maxTemp, colorMap).then(setImage);
    }, [matrix, matrix[0].length, matrix.length, minTemp, maxTemp, colorMap]);

    if (!image) return null;
    let scaleX = width / matrix[0].length;
    let scaleY = height / matrix.length;

    return (
        <KonvaImage
            image={image}
            opacity={opacity}
            scale={{ x: scaleX, y: scaleY }}
        />
    );
};

export default MatrixOverlayImage;


const inMemoryCache: Record<string, number[][]> = {};

export function getCachedMatrix(id: string): number[][] | null {
    return inMemoryCache[id] || null;
}

export function setCachedMatrix(id: string, matrix: number[][]) {
    inMemoryCache[id] = matrix;
    // Optional: persist to localStorage
    localStorage.setItem(`tempMatrix:${id}`, JSON.stringify(matrix));
}

export function getMatrixFromLocalStorage(id: string): number[][] | null {
    const stored = localStorage.getItem(`tempMatrix:${id}`);
    return stored ? JSON.parse(stored) : null;
}