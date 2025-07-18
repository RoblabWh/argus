import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
    Clock,
    Ruler,
    Image as ImageIcon,
    Map as AreaIcon,
    Copy,
    Drone,
} from "lucide-react";
import type { MappingReport } from "@/types/report";
import { add } from "date-fns";

type Props = {
    data: MappingReport | undefined;
};

export function FlightCard({ data }: Props) {
    if (!data || Object.keys(data).length === 0) {
        return (
        <Card className="min-w-52 max-w-103 flex-1 relative overflow-hidden ">
                <CardContent className="text-center text-muted-foreground">
                    No flight data available.
                </CardContent>
            </Card>
        );
    }

    const {
        flight_timestamp = "",
        address = "Unknown Location",
        flight_duration = 0,
        flight_height = 0,
        covered_area = 0,
        uav = "Unknown UAV",
        image_count = 0,
        coord = null,
    } = data;
    let shortAddress = address ?? "Unknown Location";
    
    try {
        shortAddress = address.split(",").slice(0, 2).join(", ");
    } catch (error) {
        //just truncate to first line
        shortAddress = shortAddress.length > 30 ? shortAddress.slice(0, 30) + "..." : shortAddress;
    }

    let coordinates = "No GPS Data";
    if (coord !== undefined && coord !== null) {
        coordinates = `${coord.gps?.lat.toFixed(6)}, ${coord.gps?.lon.toFixed(6)}`;

    }
    const flightDate = new Date(flight_timestamp).toLocaleString();
    const flightDurationValue = `${Math.floor(flight_duration / 60)}:${flight_duration % 60} mm:ss`; //convert seconds to minutes and seconds

    const handleCopy = async () => {
        await navigator.clipboard.writeText(address);
        toast.success("Address copied to clipboard");
    };


    return (
        <Card className="min-w-54 max-w-114 flex-1 relative overflow-hidden pb-3">
            {/* Background UAV Icon */}
            <Drone className="absolute right-2 top-2 w-24 h-24 opacity-100 text-muted-foreground dark:text-white z-0 pointer-events-none" />

            {/* Gradient Overlay */}
            <div className="absolute inset-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/60 to-white/0 dark:from-gray-900/100 dark:via-gray-900/70 dark:to-gray-900/0" />

            <CardContent className="px-4 py-3 flex flex-col items-start space-y-1 relative z-10">
                {/* Header */}
                <div className="flex justify-between items-start w-full">
                    <div className="text-xl font-semibold">{uav}</div>
                </div>

                {/* Address with Copy Button */}
                <div className="flex items-center justify-start w-full gap-1">
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <div className="text-xs text-muted-foreground truncate max-w-[12rem] cursor-help">
                                {shortAddress}
                            </div>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>{address}</p>
                        </TooltipContent>
                    </Tooltip>

                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button
                                size="icon"
                                variant="ghost"
                                className="w-4 h-4 p-0"
                                onClick={handleCopy}
                            >
                                <Copy className="w-3 h-3 text-muted-foreground" />
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Copy full address</p>
                        </TooltipContent>
                    </Tooltip>
                </div>

                {/* Coordinates */}
        <div className="text-[10px] text-muted-foreground">{coordinates}</div>


                {/* Flight Stats */}
                <div className="flex flex-col mt-2 gap-[0.2rem] text-xs text-muted-foreground">
                    <div className="flex items-center gap-2">
                        <Clock className="w-3 h-3" />
                        Duration: {flightDurationValue}
                    </div>
                    <div className="flex items-center gap-2">
                        <Ruler className="w-3 h-3" />
                        Height: {Math.round(flight_height)} m
                    </div>
                    <div className="flex items-center gap-2">
                        <AreaIcon className="w-3 h-3" />
                        Area: {Math.round(covered_area)} m²
                    </div>
                    <div className="flex items-center gap-2">
                        <ImageIcon className="w-3 h-3" />
                        Images: {image_count}
                    </div>
                </div>

                {/* Footer */}
                <div className="w-full text-right mt-1 flex justify-end text-[10px] text-muted-foreground">
                    <span>Flown at {flightDate}</span>
                </div>
            </CardContent>
        </Card>
    );
}
