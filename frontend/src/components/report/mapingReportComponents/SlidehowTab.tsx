import React, { useRef, useEffect, useState } from "react";
import { Stage, Layer, Image as KonvaImage } from "react-konva";
import useImage from "use-image";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { getApiUrl } from "@/api";
import { useAspectRatio } from "@/hooks/useAspectRatio";
import type { Image } from "@/types/image";

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

    const [backgroundImageUrl, setBackgroundImageUrl] = useState<string | null>(null);
    const [backgroundImage] = useImage(backgroundImageUrl || "");
    const [opacity, setOpacity] = useState(1);

    const dummy_scale = 0.44; // Default scale for thermal images

    // Resize canvas to fit container
    useEffect(() => {
        if (!containerRef.current) return;

        const observeResize = () => {
            const el = containerRef.current!;
            const observer = new ResizeObserver(([entry]) => {
                const { width, height } = entry.contentRect;
                // leave some space for controls
                const adjustedHeight = height - 100; // tweak as needed
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

        setImageUrl(`${apiUrl}/${selectedImage.url}`);
        setOpacity(1);

        if (selectedImage.thermal && selectedImage.thermal_data?.counterpart_id) {
            const rgbImage = images.find(img => img.id === selectedImage.thermal_data?.counterpart_id);
            if (rgbImage) {
                console.log("Setting background image for thermal counterpart:", rgbImage.filename);
                setBackgroundImageUrl(`${apiUrl}/${rgbImage.url}`);
            } else {
                setBackgroundImageUrl(null); // fallback
            }
        } else {
            setBackgroundImageUrl(null);
        }
    }, [selectedImage, images]);

    // Fit and center image when loaded or canvas size changes
    useEffect(() => {
        if (!image || !containerSize.width || !containerSize.height) return;

        const scaleX = containerSize.width / image.width;
        const scaleY = containerSize.height / image.height;
        const fitScale = Math.min(scaleX, scaleY);

        const offsetX = (containerSize.width - image.width * fitScale) / 2;
        const offsetY = (containerSize.height - image.height * fitScale) / 2;

        resetView();
    }, [image, containerSize]);

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
    };

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
                        >
                            <Layer>
                                {/* Background RGB image (if exists) */}
                                {backgroundImage && selectedImage?.thermal && selectedImage.thermal_data?.counterpart_scale && (
                                    <KonvaImage
                                        image={backgroundImage}
                                        scale={{
                                            x: dummy_scale,
                                            y: dummy_scale,
                                        }}
                                        x={image ? -(backgroundImage.width * dummy_scale - image.width)  : 0}
                                        y={image ? -(backgroundImage.height * dummy_scale - image.height) : 0}
                                        opacity={1}
                                    />
                                )}

                                {/* Foreground thermal image */}
                                {image && (
                                    <KonvaImage
                                        image={image}
                                        opacity={opacity}
                                    />
                                )}
                            </Layer>
                        </Stage>
                        {selectedImage?.thermal && selectedImage.thermal_data?.counterpart_id && (
                            <div className="absolute translate-y-[-100%] left-1/2 transform -translate-x-1/2 w-48 z-50">
                                <Slider
                                    defaultValue={[100]}
                                    max={100}
                                    min={0}
                                    step={1}
                                    onValueChange={([val]) => setOpacity(val / 100)}
                                />
                                <p className="text-xs text-center mt-1 text-muted-foreground">Thermal Opacity</p>
                            </div>
                        )}
                    </>

                ) : (
                    <p>No image selected</p>
                )}
            </div>

            <div className="grid grid-cols-3 items-center justify-between my-4 p-4 w-full bg-white dark:bg-gray-800">
                <div className="text-sm text-muted-foreground">
                    {selectedImage?.filename ?? ""}
                </div>

                <div className="flex items-center gap-4 w-full justify-center">
                    <Button variant="default" onClick={previousImage}>
                        <ArrowLeft />
                    </Button>
                    <Button variant="default" onClick={nextImage}>
                        <ArrowRight />
                    </Button>
                </div>

                <div className="flex items-center justify-end gap-2">
                    <Button variant="outline" onClick={resetView}>
                        Reset View
                    </Button>
                </div>
            </div>
        </div>
    );
};
