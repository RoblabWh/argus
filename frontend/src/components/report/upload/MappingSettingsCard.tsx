import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardFooter
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    Switch
} from "@/components/ui/switch";
import {
    Input
} from "@/components/ui/input";
import {
    Label
} from "@/components/ui/label";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { useState, useEffect } from "react";
import { Info, Blocks, Drone } from "lucide-react";
import { MappingTile } from "@/components/report/upload/SettingsTile";

type MappingSettingsProps = {
    weatherAvailable: boolean;
    imagesContainAltitude: boolean;
    handleStartProcessing: () => void;
    processButtonActive: boolean;
    status: string;
    progress?: number;
};
// ...imports remain the same

export function MappingSettingsCard({
    weatherAvailable,
    imagesContainAltitude,
    handleStartProcessing,
    processButtonActive,
    status,
    progress
}: MappingSettingsProps) {
    const [keepWeather, setKeepWeather] = useState(false);
    const [fastMapping, setFastMapping] = useState(true);
    const [tiltDeviation, setTiltDeviation] = useState("7.5");
    const [mapSize, setMapSize] = useState("medium");
    const [defaultAltitude, setDefaultAltitude] = useState("");
    const [useDefaultAltitude, setUseDefaultAltitude] = useState(!imagesContainAltitude);
    const [useODM, setUseODM] = useState(false);
    const [odmMode, setOdmMode] = useState("fast");

    useEffect(() => {
        setUseDefaultAltitude(!imagesContainAltitude);
    }, [imagesContainAltitude]);

    const tileBaseClasses = "rounded-2xl border-2 border-primary p-4"// bg-muted bg-gradient-to-tl from-primary/15 via-white/0 to-white/0 dark:from-gray-700/70 dark:via-gray-900/0 dark:to-gray-900/0";

    return (
        <Card className="w-full">
            <CardHeader>
                <CardTitle>Processing Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">

                <div className="flex flex-row gap-4 flex-wrap">
                    
                    {/* Always-open General Settings Tile */}
                    <div className={cn(tileBaseClasses, "space-y-4 transition-all duration-300")}>

                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-semibold">General Settings</h3>
                        </div>

                        <div className="flex items-center justify-between gap-6 ">
                            <div className="flex items-center gap-2">
                                <Label htmlFor="keep-weather">Keep weather</Label>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Info className="w-4 h-4 text-muted-foreground cursor-help" />
                                    </TooltipTrigger>
                                    <TooltipContent side="right">
                                        Only available if weather was set before. If unchecked, weather data may be overwritten.
                                    </TooltipContent>
                                </Tooltip>
                            </div>
                            <Switch
                                id="keep-weather"
                                disabled={!weatherAvailable}
                                checked={keepWeather}
                                onCheckedChange={setKeepWeather}
                            />
                        </div>
                    </div>

                    {/* Mapping Option Tiles */}
                    <MappingTile
                        title="Fast Mapping"
                        icon={<Blocks className="w-28 h-28" />}
                        enabled={fastMapping}
                        onToggle={setFastMapping}
                    >
                        {/* Fast Mapping */}


                        <div className="relative grid md:grid-cols-2 gap-4 z-10">
                            <div className="relative flex flex-col space-y-1">
                                <Label htmlFor="map-size">Map Size</Label>
                                <Select value={mapSize} onValueChange={setMapSize}>
                                    <SelectTrigger id="map-size" className="bg-white/70 dark:bg-gray-800/70 cursor-pointer">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent className="bg-white dark:bg-gray-900">
                                        <SelectItem value="small">Small (2048×2048)</SelectItem>
                                        <SelectItem value="medium">Medium (4096×4096)</SelectItem>
                                        <SelectItem value="large">Large (8192×8192)</SelectItem>
                                        <SelectItem value="huge">Huge (16384×16384)</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="flex flex-col space-y-1">
                                <Label htmlFor="tilt-deviation">Tilt Deviation (°)</Label>
                                <Input
                                    id="tilt-deviation"
                                    type="number"
                                    min={1}
                                    max={45}
                                    step={0.1}
                                    value={tiltDeviation}
                                    onChange={(e) => setTiltDeviation(e.target.value)}
                                    className="bg-white/70 dark:bg-gray-800/70"
                                />
                            </div>
                        </div>

                        {!imagesContainAltitude && (
                            <div className="relative z-10 flex flex-col space-y-1">
                                <Label htmlFor="default-altitude">Default Altitude (m)</Label>
                                <Input
                                    id="default-altitude"
                                    type="number"
                                    min={1}
                                    max={9999}
                                    step={0.1}
                                    value={defaultAltitude}
                                    className="bg-white/70 dark:bg-gray-800/70"
                                    onChange={(e) => setDefaultAltitude(e.target.value)}
                                />
                            </div>
                        )}
                    </MappingTile>

                    {/* ODM Mapping */}
                    <MappingTile
                        title="ODM Mapping"
                        icon={<Drone className="w-28 h-28" />}
                        enabled={useODM}
                        onToggle={setUseODM}
                    >

                        <div className="relative flex flex-col space-y-1 z-10">
                            <Label htmlFor="odm-mode">ODM Mode</Label>
                            <Select value={odmMode} onValueChange={setOdmMode}>
                                <SelectTrigger id="odm-mode" className="bg-white/70 dark:bg-gray-800/70 cursor-pointer w-full">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="bg-white dark:bg-gray-900">
                                    <SelectItem value="fast">Fast Orthophoto</SelectItem>
                                    <SelectItem value="full">Full 3D Mapping</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </MappingTile>
                </div>
            </CardContent>
            <CardFooter className="flex justify-end items-center gap-4">
                {/* Show progress bar if processing */}
                {((status === "processing" ||
                    status === "preprocessing" ||
                    status === "queued") && progress !== undefined) ? (
                        <div className="w-full ">
                            <p className="text-sm text-muted-foreground mt-1 opacity-0">
                                {status} — {Math.round(progress)}%
                            </p>
                            <Progress value={progress} />
                            <p className="text-sm text-muted-foreground mt-1">
                                {status} — {Math.round(progress)}%
                            </p>
                        </div>
                    ) : (
                        <div className="w-full ">
                            <p className="text-sm text-muted-foreground mt-1 opacity-0">
                                not running
                            </p>
                            <Progress value={0} className="opacity-0" />
                            <p className="text-sm text-muted-foreground mt-1 opacity-0">
                                {status} — {Math.round(0)}%
                            </p>
                        </div>
                    )
                    }
                <Button
                    className=""
                    onClick={handleStartProcessing}
                    disabled={processButtonActive}
                >
                    Start Processing
                </Button>
            </CardFooter>
        </Card>
    );
}
