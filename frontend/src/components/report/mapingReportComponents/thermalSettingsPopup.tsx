import { useState, useEffect } from "react"
import {
    Dialog, DialogContent, DialogDescription,
    DialogFooter, DialogHeader, DialogTitle,
    DialogClose
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"


export type ThermalSettings = {
    probeRadius: number;
    recolor: boolean;
    autoTempLimits: boolean;
    minTemp: number;
    maxTemp: number;
    colorMap: string;
}

interface ThermalSettingsPopupProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    settings: ThermalSettings | null;
    onSave: (settings: ThermalSettings) => void;
}

export function ThermalSettingsPopup({ open, onOpenChange, settings, onSave }: ThermalSettingsPopupProps) {
    const [formData, setFormData] = useState<ThermalSettings>({
        probeRadius: 4,
        recolor: false,
        autoTempLimits: false,
        minTemp: 0,
        maxTemp: 100,
        colorMap: "whiteHot",
        ...settings
    });

    useEffect(() => {
        if (settings) {
            setFormData(settings);
        }
    }, [settings]);

    const handleChange = (name: keyof ThermalSettings, value: any) => {
        setFormData((prev) => ({
            ...prev,
            [name]: value
        }));
    };

    const handleSave = (e: React.FormEvent) => {
        e.preventDefault();
        onSave(formData);
        onOpenChange(false);
    };

    const recolorDisabled = !formData.recolor;
    const minMaxDisabled = recolorDisabled || formData.autoTempLimits;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <form onSubmit={handleSave}>
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>Thermal analysis settings</DialogTitle>
                        <DialogDescription>
                            Configure the probe settings and appearance of thermal images.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">

                        <div className="flex items-center justify-between">
                            <Label htmlFor="probeRadius">Probe Radius</Label>
                            <Input
                                type="number"
                                id="probeRadius"
                                name="probeRadius"
                                min={1}
                                value={formData.probeRadius}
                                onChange={(e) => handleChange("probeRadius", parseFloat(e.target.value))}
                                className="w-24"
                            />
                        </div>

                        <div className="flex items-center justify-between">
                            <Label htmlFor="recolor">Recolor</Label>
                            <Switch
                                id="recolor"
                                checked={formData.recolor}
                                onCheckedChange={(val) => handleChange("recolor", val)}
                            />
                        </div>
                        <div className={`grid gap-0 p-0 rounded-md ${recolorDisabled ? 'cursor-not-allowed text-muted-foreground bg-gray-100 dark:bg-gray-900' : ''}`}>

                            <div className="grid gap-4 p-4 pb-2 rounded-md">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="colorMap">Colormap</Label>
                                <Select
                                    disabled={recolorDisabled}
                                    value={formData.colorMap}
                                    onValueChange={(val) => handleChange("colorMap", val)}
                                >
                                    <SelectTrigger className="w-[150px]">
                                        <SelectValue placeholder="Select colormap" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="whiteHot">White Hot</SelectItem>
                                        <SelectItem value="blackHot">Black Hot</SelectItem>
                                        <SelectItem value="ironbow">Ironhot</SelectItem>
                                        <SelectItem value="rainbow">Rainbow</SelectItem>
                                        <SelectItem value="whspecial">WHspecial</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="flex items-center justify-between">
                                <Label htmlFor="autoTempLimits">Auto Temp Limits</Label>
                                <Switch
                                    id="autoTempLimits"
                                    disabled={recolorDisabled}
                                    checked={formData.autoTempLimits}
                                    onCheckedChange={(val) => handleChange("autoTempLimits", val)}
                                />
                            </div>
                            </div>
                            <div className={`grid gap-4 p-4 rounded-md ${minMaxDisabled ? ' bg-gray-100 dark:bg-gray-900 cursor-not-allowed text-muted-foreground' : ''}`}>
                                <div className="flex items-center justify-between">
                                    <Label htmlFor="minTemp">Min Temp (°C)</Label>
                                    <Input
                                        type="number"
                                        id="minTemp"
                                        name="minTemp"
                                        disabled={minMaxDisabled}
                                        value={formData.minTemp}
                                        onChange={(e) => handleChange("minTemp", parseFloat(e.target.value))}
                                        className="w-24"
                                    />
                                </div>

                                <div className="flex items-center justify-between">
                                    <Label htmlFor="maxTemp">Max Temp (°C)</Label>
                                    <Input
                                        type="number"
                                        id="maxTemp"
                                        name="maxTemp"
                                        disabled={minMaxDisabled}
                                        value={formData.maxTemp}
                                        onChange={(e) => handleChange("maxTemp", parseFloat(e.target.value))}
                                        className="w-24"
                                    />
                                </div>
                            </div>
                        </div>

                    </div>
                    <DialogFooter>
                        <DialogClose asChild>
                            <Button variant="outline">Cancel</Button>
                        </DialogClose>
                        <Button onClick={(e) => handleSave(e)}>Apply Changes</Button>
                    </DialogFooter>
                </DialogContent>
            </form>
        </Dialog>
    );
}