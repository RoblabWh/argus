import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
    Bot,
    Image as ImageIcon,
    Map as AreaIcon,
    Copy,
    Drone,
} from "lucide-react";
import type { MappingReport } from "@/types/report";

type Props = {
    description: string | undefined;
    onGenerateDescription?: () => void;
};

export function AutoDescriptionCard({ description }: Props) {
    if (!description || description.trim() === "") {
        description = "No description available. Please generate a description.";
    }


    return (
        <Card className="min-w-80 flex-1 relative overflow-hidden pb-3">
            {/* Background UAV Icon */}
            <Bot className="absolute right-2 top-2 w-24 h-24 opacity-100 text-muted-foreground dark:text-white z-0 pointer-events-none" />

            {/* Gradient Overlay */}
            <div className="absolute inset-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/60 to-white/0 dark:from-gray-900/100 dark:via-gray-900/70 dark:to-gray-900/0" />

            <CardContent className="px-4 py-3 flex flex-col items-start space-y-1 relative z-10">
                {/* Header */}
                <div className="flex justify-between items-start w-full">
                    <div className="text-xl font-semibold">AI Description</div>
                </div>

                <div className="text-[10px] text-muted-foreground">{description}</div>
                {/* (re) generate description button */}
                <Button
                    variant="outline"
                    className="mt-2"
                    onClick={() => {
                        toast.success("Regenerating AI description...");
                    }}
                >
                    Regenerate Description
                </Button>
            </CardContent>
        </Card>
    );
}
