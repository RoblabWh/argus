import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
    ChevronFirst,
    ChevronLast,
    Image as ImageIcon,
    Map as AreaIcon,
    Copy,
    Map,
    Drone,
} from "lucide-react";
import type { ReportSummary } from "@/types/report";
import { add } from "date-fns";



type Props = {
    data: ReportSummary[] | undefined;
};

export function FlightGroupCard({ data = [] }: Props) {
    if (!data || Object.keys(data).length === 0 || data === undefined) {
        return (
            <Card className="min-w-52 max-w-103 flex-1 relative overflow-hidden ">
                <CardContent className="text-center text-muted-foreground">
                    No Flights  Found.
                </CardContent>
            </Card>
        );
    }

    data.sort((a, b) => (a.flight_timestamp > b.flight_timestamp ? 1 : -1));
    const firstFlight = data[0];
    const hasMoreThanOneFlight = data.length > 1;

    let lastFlight = data[data.length - 1];
    for (let i = data.length - 1; i >= 0; i--) {
        if (data[i].flight_timestamp && i > 0) {
            lastFlight = data[i];
            break;
        } else if (i === 0) {
            lastFlight = data[data.length - 1]; // Fallback to last flight then with no valid timestamp
        }
    }
    const total_images = data.reduce((acc, flight) => acc + (flight.image_count || 0), 0);
    const total_maps = data.reduce((acc, flight) => acc + (flight.maps.length || 0), 0);

    return (
        <Card className="min-w-80 max-w-480 flex-2 relative overflow-hidden pb-3">
            {/* Background UAV Icon */}
            <Drone className="absolute right-2 top-1 w-24 h-24 opacity-100 text-muted-foreground dark:text-white z-0 pointer-events-none" />

            {/* Gradient Overlay */}
            {/* <div className="absolute inset-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/60 to-white/0 dark:from-gray-900/100 dark:via-gray-900/70 dark:to-gray-900/0" /> */}
            <div className="absolute w-40 h-30 right-0 top-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/75 to-white/55 dark:from-gray-900/100 dark:via-gray-900/85 dark:to-gray-900/60" />

            <CardContent className="px-4 pt-1 flex flex-col items-start space-y-1 relative z-10">
                {/* Header */}
                <div className="flex justify-between items-start w-full">
                    <div className="text-xl font-bold leading-none whitespace-nowrap truncate">{data.length} Flight(s)</div>
                </div>

                <div className="flex flex-col justify-start w-full gap-0 text-xs mb-0 mt-2">
                    <p className="text-sm text-muted-foreground">
                        <ChevronFirst className="inline w-3 h-3 mr-1" />
                        First flight: {new Date(firstFlight.flight_timestamp).toLocaleDateString()} at{" "}
                        {new Date(firstFlight.flight_timestamp).toLocaleTimeString()}
                    </p>
                    {hasMoreThanOneFlight && (
                        <p className="text-sm text-muted-foreground">
                            <ChevronLast className="inline w-3 h-3 mr-1" />
                            Last flight: {(lastFlight.flight_timestamp ? new Date(lastFlight.flight_timestamp).toLocaleDateString() : "Unknown")}
                            {(lastFlight.flight_timestamp ? " at " + new Date(lastFlight.flight_timestamp).toLocaleTimeString() : "")}
                        </p>
                    )}
                    <p className="text-sm text-muted-foreground pt-1">
                        <ImageIcon className="inline w-3 h-3 mr-1" />
                        Total images: {total_images}
                    </p>
                    <p className="text-sm text-muted-foreground">
                        <Map className="inline w-3 h-3 mr-1" />
                        Orthophotos: {total_maps}
                    </p>
                </div>
            </CardContent>
        </Card>
    );
}
