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
import { useEffect, useRef } from "react";
import { Info, Blocks } from "lucide-react";
import { WebODMLogo } from "@/components/report/mappingReportComponents/WebOdmCard";
import { MappingTile } from "@/components/report/upload/SettingsTile";
import type { ProcessingSettings } from "@/types/processing";
import { useReportSettings } from "@/hooks/useReportSettingsCache";
import { getProcessingSettings } from "@/api";
import { useQuery } from "@tanstack/react-query";

type MappingSettingsProps = {
    reportId: number;
    weatherAvailable: boolean;
    showManualAltitudeField: boolean;
    showFovField: boolean;
    showCamPitchField: boolean;
    showCamOrientationField: boolean;
    handleStartProcessing: (settings: ProcessingSettings) => void;
    processButtonActive: boolean;
    status: string;
    progress?: number;
    onCancelEditing?: () => void; // Optional callback for canceling editing
    isEditing?: boolean; // Optional prop to control editing state
    isWebODMAvailable?: boolean; // Optional prop to check if WebODM is available
};

export function MappingSettingsCard({
    reportId,
    weatherAvailable,
    showManualAltitudeField,
    showFovField,
    showCamPitchField,
    showCamOrientationField,
    handleStartProcessing,
    processButtonActive,
    status,
    progress,
    onCancelEditing,
    isEditing,
    isWebODMAvailable
}: MappingSettingsProps) {
    const { settings, setSettings } = useReportSettings(reportId, {
        keep_weather: weatherAvailable,
    });

    // Fetch last-used settings from backend and seed the form once
    const { data: backendSettings, isFetching: isBackendSettingsFetching } = useQuery({
        queryKey: ["processing-settings", reportId],
        queryFn: () => getProcessingSettings(reportId),
        refetchOnMount: 'always',
        staleTime: 0,
    });

    const hasInitialized = useRef(false);
    useEffect(() => {
        if (backendSettings && !isBackendSettingsFetching && !hasInitialized.current) {
            hasInitialized.current = true;
            const overrides: Partial<ProcessingSettings> = {};
            for (const [k, v] of Object.entries(backendSettings)) {
                if (v !== null && v !== undefined) {
                    (overrides as Record<string, unknown>)[k] = v;
                }
            }
            if (Object.keys(overrides).length > 0) {
                setSettings({ ...settings, ...overrides });
            }
        }
    }, [backendSettings, isBackendSettingsFetching, settings, setSettings]);

    useEffect(() => {
        if (!settings.apply_manual_defaults) return;

        const partial: Partial<ProcessingSettings> = {};
        if (showManualAltitudeField && settings.default_flight_height == null) {
            partial.default_flight_height = 100.0;
        }
        if (showFovField && settings.default_fov == null) {
            partial.default_fov = 82.0;
        }
        if (showCamPitchField && settings.default_cam_pitch == null) {
            partial.default_cam_pitch = -90.0;
        }

        if (Object.keys(partial).length > 0) {
            setSettings({ ...settings, ...partial });
        }
    }, [
        settings,
        setSettings,
        showManualAltitudeField,
        showFovField,
        showCamPitchField,
    ]);

    const processingButtonLabel = isEditing ? "Reprocess" : "Start Processing";

    const update = (partial: Partial<ProcessingSettings>) => {
        console.log("Updating settings:", partial);
        setSettings({ ...settings, ...partial });
    };

    const handleToggleAll = (val: boolean) => {
        const partial: Partial<ProcessingSettings> = { apply_manual_defaults: val };
        if (showManualAltitudeField) partial.default_flight_height = val ? (settings.default_flight_height ?? 100.0) : null;
        if (showFovField) partial.default_fov = val ? (settings.default_fov ?? 82.0) : null;
        if (showCamPitchField) partial.default_cam_pitch = val ? (settings.default_cam_pitch ?? -90.0) : null;
        update(partial);
    };

    const withVisibleManualDefaults = (current: ProcessingSettings): ProcessingSettings => {
        if (!current.apply_manual_defaults) return current;

        return {
            ...current,
            default_flight_height:
                showManualAltitudeField && current.default_flight_height == null
                    ? 100.0
                    : current.default_flight_height,
            default_fov:
                showFovField && current.default_fov == null
                    ? 82.0
                    : current.default_fov,
            default_cam_pitch:
                showCamPitchField && current.default_cam_pitch == null
                    ? -90.0
                    : current.default_cam_pitch,
        };
    };

    const handleStartProcessingWithSettings = () => {
        handleStartProcessing(withVisibleManualDefaults(settings));
    };

    const tileBaseClasses = "rounded-2xl border-2 border-primary p-4";

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
                                checked={settings.keep_weather}
                                onCheckedChange={(val) => { update({ keep_weather: val }) }}
                            />
                        </div>

                        <div className="flex items-center justify-between gap-6 ">
                            <div className="flex items-center gap-2">
                                <Label htmlFor="reread-metadata">Reload image metadata</Label>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Info className="w-4 h-4 text-muted-foreground cursor-help" />
                                    </TooltipTrigger>
                                    <TooltipContent side="right">
                                        Re-extract metadata from all images. May be needed after updates to run mapping successfully.
                                    </TooltipContent>
                                </Tooltip>
                            </div>
                            <Switch
                                id="reread-metadata"
                                checked={settings.reread_metadata}
                                onCheckedChange={(val) => { update({ reread_metadata: val }) }}
                            />
                        </div>
                    </div>

                    {/* Mapping Option Tiles */}
                    <MappingTile
                        title="Fast Mapping"
                        icon={<Blocks className="w-28 h-28" />}
                        enabled={settings.fast_mapping}
                        onToggle={(val) => update({ fast_mapping: val })}
                    >
                        <div className="relative grid md:grid-cols-2 gap-4 z-10">
                            <div className="relative flex flex-col space-y-1">
                                <div className="flex items-center gap-2">
                                    <Label htmlFor="map-size">Map Size</Label>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <Info className="w-4 h-4 text-muted-foreground cursor-help" />
                                        </TooltipTrigger>
                                        <TooltipContent side="right">
                                            Target size for widest side of final orthophoto.
                                        </TooltipContent>
                                    </Tooltip>
                                </div>
                                <Select value={"" + settings.target_map_resolution} onValueChange={(val) => { const v = parseInt(val, 10); update({ target_map_resolution: v }) }}>
                                    <SelectTrigger id="map-size" className="bg-white/70 dark:bg-gray-800/70 cursor-pointer">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent className="bg-white dark:bg-gray-900">
                                        <SelectItem value="2048">Small (2048px)</SelectItem>
                                        <SelectItem value="4096">Medium (4096px)</SelectItem>
                                        <SelectItem value="6144">Large (6144px)</SelectItem>
                                        <SelectItem value="8192">Huge (8192px)</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="flex flex-col space-y-1">
                                <div className="flex items-center gap-2">
                                    <Label htmlFor="tilt-deviation">Tilt Deviation (°)</Label>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <Info className="w-4 h-4 text-muted-foreground cursor-help" />
                                        </TooltipTrigger>
                                        <TooltipContent side="right">
                                            Camera/ gimbal threshold for images used in mapping (deviation of 0° would be images looking straight down).
                                        </TooltipContent>
                                    </Tooltip>
                                </div>
                                <Input
                                    id="tilt-deviation"
                                    type="number"
                                    min={1.0}
                                    max={50.0}
                                    step={0.1}
                                    value={settings.accepted_gimbal_tilt_deviation}
                                    onChange={(e) => update({ accepted_gimbal_tilt_deviation: parseFloat(e.target.value) })}
                                    className="bg-white/70 dark:bg-gray-800/70"
                                />
                            </div>
                        </div>

                        {/* Missing Mapping Data — single master toggle */}
                        {(showManualAltitudeField || showFovField || showCamPitchField || showCamOrientationField) && (
                            <div className="relative z-10 flex flex-col space-y-3">
                                <div className="flex items-center justify-between gap-4">
                                    <div className="flex items-center gap-2">
                                        <Label>Missing Mapping Data</Label>
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <Info className="w-4 h-4 text-muted-foreground cursor-help" />
                                            </TooltipTrigger>
                                            <TooltipContent side="right">
                                                Some images are missing required mapping data. Provide fallback values here so these images can still be included in the map.
                                            </TooltipContent>
                                        </Tooltip>
                                    </div>
                                    <Switch
                                        checked={settings.apply_manual_defaults}
                                        onCheckedChange={handleToggleAll}
                                    />
                                </div>
                                {settings.apply_manual_defaults && (
                                    <div className="space-y-3 pl-1">
                                        {showManualAltitudeField && (
                                            <div className="flex flex-col space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <Label htmlFor="default-altitude">Default Altitude (m)</Label>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Info className="w-4 h-4 text-muted-foreground cursor-help" />
                                                        </TooltipTrigger>
                                                        <TooltipContent side="right">
                                                            Used to map images without exif data about the relative altitude above ground level.
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </div>
                                                <Input
                                                    id="default-altitude"
                                                    type="number"
                                                    min={1}
                                                    max={9999}
                                                    step={0.1}
                                                    value={settings.default_flight_height ?? 100.0}
                                                    onChange={(e) => update({ default_flight_height: Number(e.target.value) })}
                                                    className="bg-white/70 dark:bg-gray-800/70"
                                                />
                                            </div>
                                        )}
                                        {showFovField && (
                                            <div className="flex flex-col space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <Label htmlFor="default-fov">Default FOV (°)</Label>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Info className="w-4 h-4 text-muted-foreground cursor-help" />
                                                        </TooltipTrigger>
                                                        <TooltipContent side="right">
                                                            Camera field-of-view in degrees — applied to images where FOV was missing.
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </div>
                                                <Input
                                                    id="default-fov"
                                                    type="number"
                                                    min={1}
                                                    max={180}
                                                    step={0.1}
                                                    value={settings.default_fov ?? 82.0}
                                                    onChange={(e) => update({ default_fov: Number(e.target.value) })}
                                                    className="bg-white/70 dark:bg-gray-800/70"
                                                />
                                            </div>
                                        )}
                                        {showCamPitchField && (
                                            <div className="flex flex-col space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <Label htmlFor="default-cam-pitch">Default Camera Pitch (°)</Label>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Info className="w-4 h-4 text-muted-foreground cursor-help" />
                                                        </TooltipTrigger>
                                                        <TooltipContent side="right">
                                                            Camera tilt in degrees. -90 = straight down (nadir).
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </div>
                                                <Input
                                                    id="default-cam-pitch"
                                                    type="number"
                                                    min={-90}
                                                    max={90}
                                                    step={0.1}
                                                    value={settings.default_cam_pitch ?? -90.0}
                                                    onChange={(e) => update({ default_cam_pitch: Number(e.target.value) })}
                                                    className="bg-white/70 dark:bg-gray-800/70"
                                                />
                                            </div>
                                        )}
                                        {showCamOrientationField && (
                                            <div className="flex flex-col space-y-1">
                                                <Label htmlFor="cam-orientation-source">Camera Orientation Source</Label>
                                                <Select
                                                    value={settings.cam_orientation_source}
                                                    onValueChange={(val: "uav" | "manual") => update({ cam_orientation_source: val })}
                                                >
                                                    <SelectTrigger id="cam-orientation-source" className="bg-white/70 dark:bg-gray-800/70 cursor-pointer">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent className="bg-white dark:bg-gray-900">
                                                        <SelectItem value="uav">UAV (from telemetry)</SelectItem>
                                                        <SelectItem value="manual">Manual</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                                {settings.cam_orientation_source === "manual" && (
                                                    <div className="grid grid-cols-2 gap-3 mt-2">
                                                        <div className="flex flex-col space-y-1">
                                                            <Label htmlFor="default-cam-yaw">Yaw (°)</Label>
                                                            <Input
                                                                id="default-cam-yaw"
                                                                type="number"
                                                                min={-180}
                                                                max={180}
                                                                step={0.1}
                                                                value={settings.default_cam_yaw ?? ""}
                                                                onChange={(e) => update({ default_cam_yaw: e.target.value === "" ? null : Number(e.target.value) })}
                                                                className="bg-white/70 dark:bg-gray-800/70"
                                                            />
                                                        </div>
                                                        <div className="flex flex-col space-y-1">
                                                            <Label htmlFor="default-cam-roll">Roll (°)</Label>
                                                            <Input
                                                                id="default-cam-roll"
                                                                type="number"
                                                                min={-180}
                                                                max={180}
                                                                step={0.1}
                                                                value={settings.default_cam_roll ?? ""}
                                                                onChange={(e) => update({ default_cam_roll: e.target.value === "" ? null : Number(e.target.value) })}
                                                                className="bg-white/70 dark:bg-gray-800/70"
                                                            />
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}
                    </MappingTile>

                    {/* ODM Mapping */}
                    <MappingTile
                        title="ODM Mapping"
                        icon={<WebODMLogo key="odm-logo-settings" className="w-28 h-28" />}
                        enabled={settings.odm_processing}
                        onToggle={(val) => update({ odm_processing: val })}
                        inactive={!isWebODMAvailable}
                        inactiveTooltip={!isWebODMAvailable ? "WebODM is not available" : undefined}
                    >

                        <div className="relative flex flex-col space-y-1 z-10">
                            <Label htmlFor="odm-mode">ODM Mode</Label>
                            <Select value={settings.odm_full ? "true" : "false"} onValueChange={(val: string) => update({ odm_full: val === "true" })}>
                                <SelectTrigger id="odm-mode" className="bg-white/70 dark:bg-gray-800/70 cursor-pointer w-full">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="bg-white dark:bg-gray-900">
                                    <SelectItem value="false">Fast Orthophoto</SelectItem>
                                    <SelectItem value="true">Full 3D Mapping</SelectItem>
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
                {isEditing && (
                    <Button
                        variant="secondary"
                        onClick={onCancelEditing}
                        className="mr-2"
                    >
                        Cancel Editing
                    </Button>
                )}
                <Button
                    className=""
                    onClick={handleStartProcessingWithSettings}
                    disabled={processButtonActive}
                >
                    {processButtonActive ? "Processing..." : processingButtonLabel}
                </Button>
            </CardFooter>
        </Card>
    );
}
