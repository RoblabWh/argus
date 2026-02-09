import { Button } from "@/components/ui/button";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { AlertTriangle } from "lucide-react";

interface ThresholdWarningProps {
    detectionId: string | number;
    message?: string;
}

export function ThresholdWarning({ detectionId, message }: ThresholdWarningProps) {
    return (
        <Popover>
            <PopoverTrigger asChild>
                <Button
                    size="icon"
                    variant="outline"
                    className="text-yellow-700 hover:text-yellow-700 absolute top-4 right-4 z-50 bg-yellow-50/50 border-yellow-700 dark:bg-yellow-900/30 dark:border-yellow-400 dark:text-yellow-400 hover:dark:bg-yellow-900/50"
                    title="Threshold Warning"
                >
                    <AlertTriangle className="h-6 w-6" />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-64">
                <p className="text-sm text-muted-foreground">
                    {message ?? `Detection ${detectionId} might not be visible due to threshold settings.`}
                </p>
            </PopoverContent>
        </Popover>
    );
}
