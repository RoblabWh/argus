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
}: SlideshowControlsProps) {
    return (
        <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center mt-4 p-2 md:p-4 w-full bg-white dark:bg-gray-800 gap-2">
            {/* Filename with tooltip */}
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
