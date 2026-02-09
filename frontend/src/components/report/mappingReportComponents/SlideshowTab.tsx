import React, { useRef, useEffect, useState, useMemo } from "react";
import { Stage, Layer, Image as KonvaImage, Rect } from "react-konva";
import type { ImageBasic } from "@/types/image";
import type { Detection } from "@/types/detection";
import { ThermalSettingsPopup } from "./ThermalSettingsPopup";
import useImage from "use-image";
import { useThermalMatrix } from "@/hooks/useThermalMatrix";
import { useDeleteDetection } from "@/hooks/detectionHooks";
import { getApiUrl } from "@/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Edit, Trash, Share2, Scan } from "lucide-react";
import { useImages } from "@/hooks/imageHooks";
import { useDetections } from "@/hooks/detectionHooks";
import { useQueryClient } from "@tanstack/react-query";
import { getDetectionColor } from "@/types/detection";
import { DetectionSharePopup } from "./DetectionSharePopup";
import { DetectionEditPopup } from "./DetectionEditPopup";
import { PanoramaViewer } from "./PanoramaViewer";
import {
    TempMatrixOverlayImage,
    ThresholdWarning,
    OpacityPanel,
    SlideshowControls,
} from "./slideshow";


interface SlideshowTabProps {
    selectedImage: ImageBasic | null;
    nextImage: () => void;
    previousImage: () => void;
    thresholds: { [key: string]: number };
    visibleCategories: { [key: string]: boolean };
    report_id: number;
}

export const SlideshowTab: React.FC<SlideshowTabProps> = ({
    selectedImage,
    nextImage,
    previousImage,
    thresholds,
    visibleCategories,
    report_id,
}) => {
    const apiUrl = getApiUrl();
    const containerRef = useRef<HTMLDivElement>(null);
    const stageRef = useRef<any>(null);
    const queryClient = useQueryClient();

    const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
    const isCompactView = containerSize.width < 940;

    const [imageUrl, setImageUrl] = useState<string | null>(null);
    const [image, loadingStatus] = useImage(imageUrl || "");

    const [scale, setScale] = useState(1);
    const [minScale, setMinScale] = useState(1);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const fallbackScale = 0.475;

    const [lastTouchDistance, setLastTouchDistance] = useState<number | null>(null);
    const [touch1, setTouch1] = useState<any>(null);
    const [touch2, setTouch2] = useState<any>(null);

    const [backgroundImageUrl, setBackgroundImageUrl] = useState<string | null>(null);
    const [backgroundImageName, setBackgroundImageName] = useState<string | null>(null);
    const [backgroundImage] = useImage(backgroundImageUrl || "");
    const [opacity, setOpacity] = useState(1);
    const imageFilename = useMemo(() => {
        return `${selectedImage?.filename ?? ""} ${backgroundImageName ? `(${backgroundImageName})` : ""}`;
    }, [selectedImage, backgroundImageName]);

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
    const { data: images } = useImages(report_id);

    const [selectedDetection, setSelectedDetection] = useState<any | null>(null);
    const [shareDetectionOpen, setShareDetectionOpen] = useState(false);
    const [editOpen, setEditOpen] = useState(false);
    const handleSave = (updated: Detection) => {
        console.log("Updated detection:", updated);
    };

    const { data, isLoading, error, refetch } = useThermalMatrix(selectedImage?.id, selectedImage?.thermal);

    const [probeResult, setProbeResult] = useState<{
        x: number;
        y: number;
        probeMessage: string;
    } | null>(null);

    const { data: detections } = useDetections(report_id);
    const deleteDetectionMutation = useDeleteDetection(report_id);

    const [detectionsOfImage, setDetectionsOfImage] = useState<any[]>([]);
    useEffect(() => {
        setDetectionsOfImage(detections?.filter((d) => d.image_id === selectedImage?.id) || []);
    }, [detections, selectedImage]);

    // Highlight detections animation
    const [highlightDetections, setHighlightDetections] = useState(false);
    const [highlightPhase, setHighlightPhase] = useState(0);

    useEffect(() => {
        if (!highlightDetections) {
            setHighlightPhase(0);
            return;
        }

        const startTime = Date.now();
        const duration = 2000;
        const cycles = 3;

        const animate = () => {
            const elapsed = Date.now() - startTime;
            if (elapsed >= duration) {
                setHighlightDetections(false);
                setHighlightPhase(0);
                return;
            }
            const phase = Math.sin((elapsed / duration) * cycles * Math.PI * 2) * 0.5 + 0.5;
            setHighlightPhase(phase);
            requestAnimationFrame(animate);
        };

        requestAnimationFrame(animate);
    }, [highlightDetections]);

    useEffect(() => {
        if (data && selectedImage?.id === data.image_id) {
            if (error) {
                setTempMatrix(null);
                setMinMaxTemp({ min: 20, max: 100 });
            } else if (data.matrix) {
                setTempMatrix(data.matrix);
                const minTemp = data.min_temp || 20.0;
                const maxTemp = data.max_temp || 100.0;
                console.log("Thermal matrix loaded for image:", selectedImage.id, "Min Temp:", minTemp, "Max Temp:", maxTemp);
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
            const minTemp = data.min_temp || 20.0;
            const maxTemp = data.max_temp || 100.0;
            console.log("Thermal matrix loaded for image:", selectedImage.id, "Min Temp:", minTemp, "Max Temp:", maxTemp);
            setMinMaxTemp({ min: minTemp, max: maxTemp });
        }
    }, [tempMode]);

    useEffect(() => {
        if (!containerRef.current) return;

        const observeResize = () => {
            const el = containerRef.current!;
            const observer = new ResizeObserver(([entry]) => {
                const { width, height } = entry.contentRect;
                const adjustedHeight = height - 90;
                const size = Math.min(width, adjustedHeight);
                setContainerSize({ width: width, height: size });
            });

            observer.observe(el);
            return () => observer.disconnect();
        };

        return observeResize();
    }, []);

    // When a new image is selected, update image URL and reset scale/position
    useEffect(() => {
        if (!selectedImage) return;

        setProbeResult(null);
        setImageUrl(`${apiUrl}/${selectedImage.url}`);

        if (selectedImage.thermal && selectedImage.thermal_data?.counterpart_id) {
            if (images) {
                const rgbImage = images.find(img => img.id === selectedImage.thermal_data?.counterpart_id);
                if (rgbImage) {
                    console.log("Setting background image for thermal counterpart:", rgbImage.filename);
                    setBackgroundImageUrl(`${apiUrl}/${rgbImage.url}`);
                    setBackgroundImageName(rgbImage.filename);
                } else {
                    setBackgroundImageUrl(null);
                    setBackgroundImageName(null);
                }
            }
            if (data && selectedImage?.id === data.image_id && tempMode) {
                setTempMatrix(data.matrix);
                const minTemp = data.min_temp || 20.0;
                const maxTemp = data.max_temp || 100.0;
                console.log("Thermal matrix loaded for image:", selectedImage.id, "Min Temp:", minTemp, "Max Temp:", maxTemp);
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
        setSelectedDetection(null);
    };

    const handleSettingsSave = (settings: any) => {
        if (!settings) return;
        setThermalSettings(settings);
    };

    // Handle zoom (wheel)
    const handleWheel = (e: any) => {
        e.evt.preventDefault();
        setSelectedDetection(null);
        const scaleBy = 1.05;
        const stage = stageRef.current;
        const oldScale = stage.scaleX();

        const pointer = stage.getPointerPosition();
        if (!pointer || !image) return;

        const mousePointTo = {
            x: (pointer.x - stage.x()) / oldScale,
            y: (pointer.y - stage.y()) / oldScale,
        };

        let newScale = e.evt.deltaY > 0 ? oldScale / scaleBy : oldScale * scaleBy;
        newScale = Math.max(minScale, newScale);

        let newX = pointer.x - mousePointTo.x * newScale;
        let newY = pointer.y - mousePointTo.y * newScale;

        const scaledWidth = image.width * newScale;
        const scaledHeight = image.height * newScale;

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
        setProbeResult(null);
    };

    const handleTouchMove = (e: any) => {
        e.evt.preventDefault();

        const stage = stageRef.current;
        if (!stage || !image) return;

        const touch1 = e.evt.touches[0] || null;
        const touch2 = e.evt.touches[1] || null;
        setTouch1(touch1);
        setTouch2(touch2);

        if (touch1 && touch2) {
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
                let newScale = scale * scaleBy;
                if (newScale < minScale) newScale = minScale;

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
                stage.draggable(true);
            } else {
                handleDragMove(e);
            }
        }
    };

    const handleTouchEnd = () => {
        setLastTouchDistance(null);
        setTouch1(null);
        setTouch2(null);
        stageRef.current?.draggable(true);
    };

    const clampPosition = (pos: { x: number, y: number }, currentScale: number) => {
        if (!image) return pos;
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
        if (e.evt.touches && e.evt.touches.length > 1) return;

        const node = e.target;
        const scaledWidth = image.width * scale;
        const scaledHeight = image.height * scale;

        const maxX = 0;
        const minX = containerSize.width - scaledWidth;
        const maxY = 0;
        const minY = containerSize.height - scaledHeight;

        const clampedX = scaledWidth > containerSize.width
            ? Math.min(maxX, Math.max(minX, node.x()))
            : (containerSize.width - scaledWidth) / 2;

        const clampedY = scaledHeight > containerSize.height
            ? Math.min(maxY, Math.max(minY, node.y()))
            : (containerSize.height - scaledHeight) / 2;

        if (clampedX === node.x() && clampedY === node.y()) return;

        node.position({ x: clampedX, y: clampedY });
        setPosition({ x: clampedX, y: clampedY });
        setProbeResult(null);
    };

    const handleMouseClick = (e: any) => {
        setSelectedDetection(null);

        const stage = e.currentTarget;
        const stageScale = stage.scaleX();
        const pointer = stage.getPointerPosition();
        if (!pointer || !image) return;

        const posiOnImageX = (pointer.x - position.x) * (1 / stageScale);
        const posiOnImageY = (pointer.y - position.y) * (1 / stageScale);

        const imageWidth = image ? image.width : 0;
        const imageHeight = image ? image.height : 0;

        if (posiOnImageX < 0 || posiOnImageX > imageWidth || posiOnImageY < 0 || posiOnImageY > imageHeight) return;

        if (tempMode && selectedImage?.thermal) {
            const ix = Math.floor(posiOnImageX / 2);
            const iy = Math.floor(posiOnImageY / 2);

            let probeMessage = "";
            if (!tempMatrix) {
                probeMessage = "No reading available";
            } else {
                const sampleRadius = thermalSettings.probeRadius;
                const minX = Math.max(0, ix - sampleRadius);
                const maxX = Math.min(tempMatrix[0].length - 1, ix + sampleRadius);
                const minY = Math.max(0, iy - sampleRadius);
                const maxY = Math.min(tempMatrix.length - 1, iy + sampleRadius);

                const roi = tempMatrix.slice(minY, maxY + 1).map(row => row.slice(minX, maxX + 1));

                const maxTemp = Math.round(10 * Math.max(...roi.flat()) / 10);
                const minTemp = Math.round(10 * Math.min(...roi.flat()) / 10);

                probeMessage = `Max: ${maxTemp}°C, Min: ${minTemp}°C`;

                console.log("Probe clicked at:", posiOnImageX, posiOnImageY, "Matrix size:", tempMatrix.length, "x", tempMatrix[0].length, "trying to get:", ix, iy);
            }

            setProbeResult({
                x: pointer.x,
                y: pointer.y,
                probeMessage: probeMessage,
            });
        }
    };

    function getDetectionPopupPosition(
        det: any,
        stageRef: React.RefObject<any>,
        elementWidth: number = 50,
        elementHeight: number = 140,
        start: "right" | "left" | "top" | "bottom" = "right",
    ): { top: number; left: number } {
        if (!stageRef.current) return { top: 0, left: 0 };

        const scale = stageRef.current.scaleX() ?? 1;
        const margin = 10;

        const stageBox = stageRef.current.container().getBoundingClientRect();

        const detX = det.screenX;
        const detY = det.screenY;
        const detW = det.bbox[2] * scale;
        const detH = det.bbox[3] * scale;

        let left = detX + detW + margin;
        if (start === "left") {
            left = detX - elementWidth - margin;
        } else if (start === "top" || start === "bottom") {
            left = detX;
        }

        let top = detY;
        if (start === "bottom") {
            top = detY + detH + margin;
        } else if (start === "top") {
            top = detY - elementHeight - margin;
        }

        if (left + elementWidth > stageBox.width) {
            left = detX - elementWidth - margin;
        }

        if (top + elementHeight > stageBox.height) {
            top = detY + detH - elementHeight;
            if (top < 0) top = margin;
            else if (top + elementHeight > stageBox.height) top = stageBox.height - elementHeight - margin;
        }

        if (top < 0 && start !== "top") {
            top = margin;
        } else if (top < 0 && start === "top") {
            top = detY + detH + margin;
            if (top + elementHeight > stageBox.height) top = stageBox.height - elementHeight - margin;
        }
        if (left < 0) left = margin;

        return { top, left };
    }

    function deleteDetectionMutationHandler(detectionId: number) {
        if (!selectedImage) return;
        confirm("Are you sure you want to delete this detection? This action cannot be undone.");
        deleteDetectionMutation.mutate(detectionId, {
            onSuccess: () => {
                console.log("Detection deleted:", detectionId);
                setSelectedDetection(null);
                queryClient.invalidateQueries({ queryKey: ["detections", report_id] });
            },
            onError: (error) => {
                console.error("Error deleting detection:", error);
            }
        });
    }

    function displayHiddenDetectionsWarning(detections: any[]): boolean {
        if (!detections || detections.length === 0) return false;
        const selection = detections?.filter((det) => {
            const threshold = thresholds?.[det.class_name] ?? 0;
            return det.score < threshold;
        });
        if (selection && selection.length > 0) return true;
        const hidden = detections?.filter((det) => !visibleCategories[det.class_name]);
        if (hidden && hidden.length > 0) return true;
        return false;
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
                            <PanoramaViewer imageUrl={`${apiUrl}/${selectedImage.url}`} />
                        ) : loadingStatus === "loading" ? (
                            <div>Loading image...</div>
                        ) : loadingStatus === "failed" ? (
                            <div>Failed to load image.</div>
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
                                            <TempMatrixOverlayImage
                                                matrix={tempMatrix}
                                                width={image?.width || containerSize.width}
                                                height={image?.height || containerSize.height}
                                                minTemp={thermalSettings.autoTempLimits ? minmaxTemp.min : thermalSettings.minTemp}
                                                maxTemp={thermalSettings.autoTempLimits ? minmaxTemp.max : thermalSettings.maxTemp}
                                                colorMap={thermalSettings.colorMap as any}
                                                opacity={opacity}
                                            />
                                        )}

                                        {detectionsOfImage
                                            ?.filter((det) => {
                                                const threshold = thresholds?.[det.class_name] ?? 0;
                                                return det.score >= threshold;
                                            }).map((det) => {
                                                if (!visibleCategories[det.class_name]) return null;
                                                const [x, y, w, h] = det.bbox;
                                                const color = getDetectionColor(det.class_name);

                                                const baseStroke = 6;
                                                const strokeWidth = highlightDetections
                                                    ? baseStroke + highlightPhase * 25
                                                    : baseStroke;

                                                return (
                                                    <Rect
                                                        key={det.id}
                                                        x={x}
                                                        y={y}
                                                        width={w}
                                                        height={h}
                                                        stroke={color}
                                                        strokeWidth={strokeWidth}
                                                        onClick={(e) => {
                                                            const stage = stageRef.current;
                                                            const scale = stage.scaleX();
                                                            const pos = stage.position();

                                                            setSelectedDetection({
                                                                ...det,
                                                                screenX: x * scale + pos.x,
                                                                screenY: y * scale + pos.y,
                                                            });
                                                        }}
                                                    />
                                                );
                                            })
                                        }
                                    </Layer>
                                </Stage>

                                {displayHiddenDetectionsWarning(detectionsOfImage) && (
                                    <ThresholdWarning
                                        detectionId="global"
                                        message="Some detections are hidden due to visibility settings or threshold."
                                    />
                                )}

                                {selectedDetection && (
                                    <>
                                        <div className="absolute top-2 left-2 bg-black/50 text-white text-xs p-2 rounded-md z-50 w-33" style={getDetectionPopupPosition(selectedDetection, stageRef, 135, 50, "top")}>
                                            <div><span className="font-semibold">Class:</span> {selectedDetection.class_name}</div>
                                            <div><span className="font-semibold">Confidence:</span> {(selectedDetection.score * 100).toFixed(1)}%</div>
                                        </div>
                                        <div
                                            className="absolute flex gap-2 p-2 bg-white shadow-md rounded-lg z-50 flex-col dark:bg-gray-800"
                                            style={getDetectionPopupPosition(selectedDetection, stageRef)}
                                        >
                                            <Button
                                                size="icon"
                                                variant="outline"
                                                onClick={() => setEditOpen(true)}
                                            >
                                                <Edit />
                                            </Button>
                                            <Button
                                                size="icon"
                                                variant="outline"
                                                onClick={() => deleteDetectionMutationHandler(selectedDetection.id)}
                                            >
                                                <Trash />
                                            </Button>
                                            <Button
                                                size="icon"
                                                variant="outline"
                                                onClick={() => setShareDetectionOpen(true)}
                                            >
                                                <Share2 />
                                            </Button>
                                        </div>
                                    </>
                                )}

                                {selectedDetection && (
                                    <>
                                        <DetectionSharePopup
                                            open={!!shareDetectionOpen}
                                            onClose={() => setShareDetectionOpen(false)}
                                            detection={selectedDetection}
                                            timestamp={selectedImage?.created_at || ""}
                                            drzBackendApi="https://lets.try.this"
                                        />
                                        <DetectionEditPopup
                                            reportId={report_id}
                                            open={editOpen}
                                            timestamp={selectedImage?.created_at || ""}
                                            onClose={() => setEditOpen(false)}
                                            detection={selectedDetection}
                                            onSave={handleSave}
                                        />
                                    </>
                                )}

                                {selectedImage?.thermal && selectedImage.thermal_data?.counterpart_id && (
                                    <OpacityPanel
                                        showPanel={showOpacityPanel}
                                        onTogglePanel={() => setShowOpacityPanel(!showOpacityPanel)}
                                        onOpacityChange={setOpacity}
                                    />
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

            <SlideshowControls
                imageFilename={imageFilename}
                onPrevious={previousImage}
                onNext={nextImage}
                onResetView={resetView}
                onHighlight={() => setHighlightDetections(true)}
                tempMode={tempMode}
                onTempModeToggle={() => {
                    setTempMode(!tempMode);
                    if (tempMode) setProbeResult(null);
                }}
                onThermalSettingsOpen={() => setThermalSettingsPopupOpen(true)}
                isThermalImage={!!selectedImage?.thermal}
                hasDetections={!!detectionsOfImage?.length}
                isHighlighting={highlightDetections}
                isCompactView={isCompactView}
            />

            <ThermalSettingsPopup
                open={thermalSettingsPopupOpen}
                onOpenChange={setThermalSettingsPopupOpen}
                settings={thermalSettings}
                onSave={handleSettingsSave}
            />
        </div>
    );
};
