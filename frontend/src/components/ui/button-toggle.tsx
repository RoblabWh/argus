import { Button } from "@/components/ui/button";
import type { LucideIcon } from "lucide-react";

interface ButtonToggleProps {
    icon: LucideIcon;
    label: string;
    isToggled: boolean;
    isDisabled?: boolean;
    setIsToggled: (value: boolean) => void;
}

export function ButtonToggle({
    icon: Icon,
    label,
    isToggled,
    isDisabled,
    setIsToggled,
}: ButtonToggleProps) {
    return (
        <Button

            variant={!isToggled ? "default" : "outline"}
            onClick={() => setIsToggled(!isToggled)}
            disabled={isDisabled}
            className={`flex items-center gap-2 px-4 py-2 relative border-2 transition-colors duration-200 ${isToggled ? "border-primary ring-2 ring-primary/50" : "border-transparent"
                }`}
        >
            <Icon className="w-4 h-4" />
            <span>{label}</span>
        </Button>
    );
}
