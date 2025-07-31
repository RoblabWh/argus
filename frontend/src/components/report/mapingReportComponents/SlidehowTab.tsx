import React, { useRef, useEffect, useState } from "react";
import { Stage, Layer, Image as KonvaImage, Rect } from "react-konva";
import type { Image } from "@/types/image";
import { ThermalSettingsPopup } from "./thermalSettingsPopup";
import useImage from "use-image";
import { useThermalMatrix } from "@/hooks/useThermalMatrix";
import { getApiUrl } from "@/api";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ButtonToggle } from "@/components/ui/button-toggle";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { ChevronLeft, ChevronRight, Thermometer, Scan, Locate, MousePointer2, Wand, Settings, RotateCcw } from "lucide-react";
import { useAspectRatio } from "@/hooks/useAspectRatio";
import { set } from "date-fns";
import { m } from "motion/react";
import { PanoramaViewer } from "./panoramaViewer";




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
    const [image] = useImage(imageUrl || "");//TODO check if image is loading

    const [scale, setScale] = useState(1);
    const [minScale, setMinScale] = useState(1);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const fallbackScale = 0.475; // Default scale for thermal images

    const [lastTouchDistance, setLastTouchDistance] = useState<number | null>(null);
    const [touch1, setTouch1] = useState<any>(null);
    const [touch2, setTouch2] = useState<any>(null);

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
            if (error) {
                // console.error("Error loading thermal matrix:", error);
                setTempMatrix(null);
                setMinMaxTemp({ min: 20, max: 100 });
            } else if (data.matrix) {
                setTempMatrix(data.matrix);
                let minTemp = data.min_temp || 20.0;
                let maxTemp = data.max_temp || 100.0;
                console.log("Thermal matrix loaded for image:", selectedImage.id, "Min Temp:", minTemp, "Max Temp:", maxTemp);
                // Optionally, you can set min/max
                setMinMaxTemp({ min: minTemp, max: maxTemp });
            }
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


    const handleTouchMove = (e: any) => {
        e.evt.preventDefault(); // prevent browser zoom

        const stage = stageRef.current;
        if (!stage || !image) return;

        const touch1 = e.evt.touches[0] || null;
        const touch2 = e.evt.touches[1] || null;
        setTouch1(touch1);
        setTouch2(touch2);

        // Stop stage from dragging

        // Pinch zoom
        if (touch1 && touch2) {
            //stage.stopDrag();
            if (stage.draggable) {
                stage.draggable(false);
            }
            if (stage.isDragging()) {
                stage.stopDrag();
            }
            const dx = touch1.clientX - touch2.clientX;
            const dy = touch1.clientY - touch2.clientY;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (lastTouchDistance !== null) {
                const scaleBy = dist / lastTouchDistance;
                var newScale = scale * scaleBy; //Math.max(minScale, scale * scaleBy);
                if (newScale < minScale) newScale = minScale; // prevent zooming out too much

                const center = {
                    x: (touch1.clientX + touch2.clientX) / 2,
                    y: (touch1.clientY + touch2.clientY) / 2,
                };

                const stagePoint = {
                    x: (center.x - stage.x()) / scale,
                    y: (center.y - stage.y()) / scale,
                };

                const newPos = {
                    x: center.x - stagePoint.x * newScale,
                    y: center.y - stagePoint.y * newScale,
                };

                setScale(newScale);
                setPosition(clampPosition(newPos, newScale));
                setProbeResult(null);
            }

            setLastTouchDistance(dist);
        } else if (touch1 && !touch2) {
            if (!stage.draggable) {
                stage.draggable(true); // enable dragging if not already
            } else {
                // One finger pan
                handleDragMove(e);
            }
        }
    };

    const handleTouchEnd = () => {
        setLastTouchDistance(null);
        setTouch1(null);
        setTouch2(null);
        stageRef.current?.draggable(true); // re-enable dragging
    };

    const clampPosition = (pos: { x: number, y: number }, currentScale: number) => {
        const scaledWidth = image.width * currentScale;
        const scaledHeight = image.height * currentScale;

        let clampedX = pos.x;
        let clampedY = pos.y;

        if (scaledWidth <= containerSize.width) {
            clampedX = (containerSize.width - scaledWidth) / 2;
        } else {
            clampedX = Math.min(0, Math.max(containerSize.width - scaledWidth, pos.x));
        }

        if (scaledHeight <= containerSize.height) {
            clampedY = (containerSize.height - scaledHeight) / 2;
        } else {
            clampedY = Math.min(0, Math.max(containerSize.height - scaledHeight, pos.y));
        }

        return { x: clampedX, y: clampedY };
    };





    // Clamp dragging so image stays inside canvas
    const handleDragMove = (e: any) => {
        if (!image || !containerSize.width || !containerSize.height) return;
        if (e.evt.touches && e.evt.touches.length > 1) return; // ignore multi-touch

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

        if (clampedX === node.x() && clampedY === node.y()) return; // no change

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

        if (tempMode && selectedImage?.thermal) {//&& tempMatrix) {
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
            <div className="bg-white dark:bg-gray-800 h-full center flex items-center justify-center relative overflow-hidden flex-col">
                {selectedImage ? (
                    <>
                        {selectedImage.panoramic ? (
                            <>
                                <PanoramaViewer imageUrl={`${apiUrl}/${selectedImage.url}`} />
                            </>
                        ) : (
                            <div className="relative">
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
                                    onTouchMove={handleTouchMove}
                                    onTouchEnd={handleTouchEnd}
                                    onMouseUp={handleMouseClick}
                                    onTap={handleMouseClick}
                                    className="p-0 m-0"
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
                                {selectedImage?.thermal && selectedImage.thermal_data?.counterpart_id && (
                                    <div
                                        className={`absolute -bottom-6 z-50 left-1/2 -translate-x-1/2 transition-all duration-300 ${showOpacityPanel ? '-translate-y-1/2' : 'translate-y-[-24px]'} opacity-60 hover:opacity-100`}
                                    >
                                        <div className="flex flex-col items-center justify-center">
                                            {/* Toggle Button */}
                                            <button
                                                onClick={() => setShowOpacityPanel(!showOpacityPanel)}
                                                className={`w-8 ${showOpacityPanel ? 'h-5 hover:h-6' : 'h-6'} bg-white dark:bg-gray-800 rounded-t-md flex items-center justify-center text-xs hover:cursor-pointer duration-300`}
                                            >
                                                {showOpacityPanel ? "▼" : "▲"}
                                            </button>
                                        </div>
                                        <div
                                            className={`flex flex-row bg-white dark:bg-gray-800 rounded-lg px-2 py-2 shadow-lg relative gap-2 h-10 w.full ${showOpacityPanel ? 'display-block' : 'hidden'} transition-opacity duration-300 `}
                                        >


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
                            </div>

                        )}

                        {probeResult && (
                            <>
                                <Scan className="absolute z-50 stroke-3 w-6 h-6 text-teal-400"
                                    style={{
                                        left: probeResult.x - 12,
                                        top: probeResult.y - 12,
                                        pointerEvents: "none",
                                        mixBlendMode: "plus-darker",
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

                    </>

                ) : (
                    <p>No image selected</p>
                )}
            </div>


            <div
                className={containerSize.width < 720 ? "flex flex-row items-center justify-between gap-2 p-2 mt-4 w-full bg-white dark:bg-gray-800" :
                    "grid grid-cols-3 items-center justify-between mt-4 p-4 w-full bg-white dark:bg-gray-800"}
            >
                <Tooltip>
                    <TooltipTrigger className={`flex justify-start ${containerSize.width < 720 ? 'w-20' : 'w-auto'}`}>
                        <div className="text-sm text-muted-foreground whitespace-nowrap overflow-hidden text-ellipsis">
                            {selectedImage?.filename ?? ""} {backgroundImageName ? `(${backgroundImageName})` : ""}
                        </div>
                    </TooltipTrigger>
                    <TooltipContent>
                        <p>{selectedImage?.filename ?? ""} {backgroundImageName ? `(${backgroundImageName})` : ""}</p>
                    </TooltipContent>
                </Tooltip>

                <div className="flex items-center gap-2 w-full justify-center">
                    <Button variant="default" onClick={previousImage} className="aspect-square">
                        <ChevronLeft />
                    </Button>
                    <Button variant="default" onClick={nextImage} className="aspect-square">
                        <ChevronRight />
                    </Button>
                </div>

                <div className="flex items-center justify-end gap-2 h-6">
                    <div className={`flex items-center gap-2 ${!selectedImage?.thermal ? 'opacity-50 cursor-not-allowed' : ''}`}>
                        <ButtonToggle
                            isDisabled={!selectedImage?.thermal}
                            icon={Thermometer}
                            label="Analysis"
                            isToggled={tempMode}
                            setIsToggled={() => {
                                setTempMode(!tempMode); // disable temp mode if no matrix
                                if (tempMode) setProbeResult(null); // hide popup when disabling
                            }}
                            showLabel={containerSize.width < 720 ? false : true}
                        />

                        <Button variant="outline" onClick={() => setThermalSettingsPopupOpen(true)}
                            className={`gap-0 ${!selectedImage?.thermal ? 'opacity-50 cursor-not-allowed' : ''}`} disabled={!selectedImage?.thermal}
                        >
                            <Thermometer className="w-4 h-4 pr-0 mr-0" />
                            <Settings className="w-4 h-4 z-10" />
                        </Button>
                        <Separator orientation="vertical" className="h-6" />

                    </div>

                    <Button variant="outline" onClick={resetView}>
                        {/* depending on screen width */}
                        {containerSize.width < 720 ? (
                            <RotateCcw className="w-4 h-4 mr-1" />
                        ) : (
                            <>Reset View</>
                        )}
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

    console.log(normalized)

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
        case "ironRed":
            calcColors = (gray) => {
                //based und hsv going from 0(hue of blue) to 1(hue of  yellow), with 100% saturation and constant rising value
                var h = gray / 256 / 1.25 + 0.55; // hue from 0 to 1
                if (h > 1) h -= 1; // wrap around
                var s = 1.0;
                var l = gray / 256;
                var r, g, b;

                function hue2rgb(p, q, t) {
                    if (t < 0) t += 1;
                    if (t > 1) t -= 1;
                    if (t < 1 / 6) return p + (q - p) * 6 * t;
                    if (t < 1 / 2) return q;
                    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
                    return p;
                }

                var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
                var p = 2 * l - q;

                r = hue2rgb(p, q, h + 1 / 3);
                g = hue2rgb(p, q, h);
                b = hue2rgb(p, q, h - 1 / 3);
                return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
            }
            break;
        case "rainbowIsh":
            calcColors = (gray) => {
                gray = (gray < 0) ? 0 : (gray > 255) ? 255 : gray;
                //clip grey to 0-1.0 range
                return [
                    128 * (Math.sin(((gray / 256) - 1 / 2) * Math.PI) + 1),
                    128 * (Math.sin(((gray / 256)) * Math.PI) + 1),
                    128 * (Math.sin(((gray / 256) + 1 / 2) * Math.PI) + 1),
                ];
            };
            break;
        case "rainbow":
            calcColors = (gray) => {
                gray = (gray < 0) ? 0 : (gray > 255) ? 255 : gray;
                //clip grey to 0-1.0 range
                gray /= 256;
                var h, l, s, r, g, b;
                l = gray < 0.1 ? 0.25 + gray * 2.5 : 0.5; // value (brightness) clamped to 0.1-1.0
                s = 1.0;
                h = 1 - gray; //

                function hue2rgb(p, q, t) {
                    if (t < 0) t += 1;
                    if (t > 1) t -= 1;
                    if (t < 1 / 6) return p + (q - p) * 6 * t;
                    if (t < 1 / 2) return q;
                    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
                    return p;
                }

                var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
                var p = 2 * l - q;

                r = hue2rgb(p, q, h + 1 / 3);
                g = hue2rgb(p, q, h);
                b = hue2rgb(p, q, h - 1 / 3);
                return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
            }
            break;

        case "whspecial":
            calcColors = (gray) => [
                gray * 2.25,
                (gray < 100 ? 90 - gray * 2.25 : (gray < 200 ? gray * 2 - 200 : gray)),
                (gray < 100 ? 90 - gray * 1.75 : (gray < 200 ? gray * 2 - 200 : gray)),
            ];
            break;
        case "minmax":
            calcColors = (gray) => {
                gray = (gray < 0) ? 0 : (gray > 255) ? 255 : gray;
                //clip grey to 0-1.0 range
                gray /= 256;
                if (gray > 0.95) {
                    return [
                        255 * gray,
                        0,
                        0,
                    ];
                } else if (gray < 0.05) {
                    return [
                        0,
                        0,
                        255 * gray * 10,
                    ];
                }
                return [
                    255 * gray * 0.2,
                    255 * gray * 0.2,
                    255 * gray * 0.2,
                ];
            };
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
            let alpha = gray > 1.0 ? 255 : Math.round((1) * 255);
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