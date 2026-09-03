import { Button } from "@/components/ui/button";
import { ButtonToggle } from "@/components/ui/button-toggle";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import {
    ChevronLeft,
    ChevronRight,
    Thermometer,
    Settings,
    RotateCcw,
    Focus,
    Plus,
    Share2,
} from "lucide-react";

interface SlideshowControlsProps {
    imageFilename: string;
    onPrevious: () => void;
    onNext: () => void;
    onResetView: () => void;
    onHighlight: () => void;
    tempMode: boolean;
    onTempModeToggle: () => void;
    onThermalSettingsOpen: () => void;
    isThermalImage: boolean;
    hasDetections: boolean;
    isHighlighting: boolean;
    isCompactView: boolean;
    /** Whether the draw-a-bounding-box mode is armed */
    drawMode: boolean;
    onDrawModeToggle: () => void;
    /** False for panoramas, thermal frames and when no image is loaded */
    canDraw: boolean;
    onShareImage: () => void;
    /** False when no DRZ backend is configured or no image is selected */
    canShareImage: boolean;
}

export function SlideshowControls({
    imageFilename,
    onPrevious,
    onNext,
    onResetView,
    onHighlight,
    tempMode,
    onTempModeToggle,
    onThermalSettingsOpen,
    isThermalImage,
    hasDetections,
    isHighlighting,
    isCompactView,
    drawMode,
    onDrawModeToggle,
    canDraw,
    onShareImage,
    canShareImage,
}: SlideshowControlsProps) {
    return (
        <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center mt-4 p-2 md:p-4 w-full bg-white dark:bg-gray-800 gap-2">
            {/* Filename, with the share action next to it */}
            <div className="flex items-center gap-1 min-w-0">
                <Tooltip>
                    <TooltipTrigger asChild>
                        <div className="min-w-0">
                            <div className="text-sm text-muted-foreground truncate">
                                {imageFilename}
                            </div>
                        </div>
                    </TooltipTrigger>
                    <TooltipContent>
                        <p>{imageFilename}</p>
                    </TooltipContent>
                </Tooltip>

                {canShareImage && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={onShareImage}
                                className="size-7 shrink-0"
                            >
                                <Share2 className="w-4 h-4" />
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Send this image to the DRZ system</p>
                        </TooltipContent>
                    </Tooltip>
                )}
            </div>

            {/* Navigation buttons */}
            <div className="flex items-center justify-center gap-2">
                <Button variant="default" onClick={onPrevious} className="aspect-square">
                    <ChevronLeft />
                </Button>
                <Button variant="default" onClick={onNext} className="aspect-square">
                    <ChevronRight />
                </Button>
            </div>

            {/* Right side controls */}
            <div className="flex items-center justify-end gap-2 h-6">
                <div className={`flex items-center gap-2 ${!isThermalImage ? 'opacity-50 cursor-not-allowed' : ''}`}>
                    <ButtonToggle
                        isDisabled={!isThermalImage}
                        icon={Thermometer}
                        label="Analysis"
                        isToggled={tempMode}
                        setIsToggled={onTempModeToggle}
                        showLabel={!isCompactView}
                    />

                    <Button
                        variant="outline"
                        onClick={onThermalSettingsOpen}
                        className={`gap-0 ${!isThermalImage ? 'opacity-50 cursor-not-allowed' : ''}`}
                        disabled={!isThermalImage}
                    >
                        <Thermometer className="w-4 h-4 pr-0 mr-0" />
                        <Settings className="w-4 h-4 z-10" />
                    </Button>
                    <Separator orientation="vertical" className="h-6" />
                </div>

                <Tooltip>
                    <TooltipTrigger asChild>
                        {/* span keeps the tooltip reachable while the button is disabled */}
                        <span>
                            <Button
                                variant={drawMode ? "default" : "outline"}
                                onClick={onDrawModeToggle}
                                disabled={!canDraw}
                                className={!canDraw ? 'opacity-50' : ''}
                            >
                                <Plus className="w-4 h-4" />
                            </Button>
                        </span>
                    </TooltipTrigger>
                    <TooltipContent>
                        <p>
                            {canDraw
                                ? "Add a detection the AI missed by drawing a box on the image"
                                : "Manual detections can only be added to RGB images"}
                        </p>
                    </TooltipContent>
                </Tooltip>

                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button
                            variant={isHighlighting ? "default" : "outline"}
                            onClick={onHighlight}
                            disabled={!hasDetections || isHighlighting}
                            className={!hasDetections ? 'opacity-50' : ''}
                        >
                            <Focus className="w-4 h-4" />
                            {!isCompactView && <span className="ml-1">Highlight</span>}
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                        <p>Pulse detection boxes to make them easier to spot</p>
                    </TooltipContent>
                </Tooltip>

                <Button variant="outline" onClick={onResetView}>
                    {isCompactView ? (
                        <RotateCcw className="w-4 h-4 mr-1" />
                    ) : (
                        <>Reset View</>
                    )}
                </Button>
            </div>
        </div>
    );
}
