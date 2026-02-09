import { Slider } from "@/components/ui/slider";

interface OpacityPanelProps {
    showPanel: boolean;
    onTogglePanel: () => void;
    onOpacityChange: (opacity: number) => void;
}

export function OpacityPanel({ showPanel, onTogglePanel, onOpacityChange }: OpacityPanelProps) {
    return (
        <div
            className={`absolute -bottom-6 z-50 left-1/2 -translate-x-1/2 transition-all duration-300 ${showPanel ? '-translate-y-1/2' : 'translate-y-[-24px]'} opacity-60 hover:opacity-100`}
        >
            <div className="flex flex-col items-center justify-center">
                {/* Toggle Button */}
                <button
                    onClick={onTogglePanel}
                    className={`w-8 ${showPanel ? 'h-5 hover:h-6' : 'h-6'} bg-white dark:bg-gray-800 rounded-t-md flex items-center justify-center text-xs hover:cursor-pointer duration-300`}
                >
                    {showPanel ? "▼" : "▲"}
                </button>
            </div>
            <div
                className={`flex flex-row bg-white dark:bg-gray-800 rounded-lg px-2 py-2 shadow-lg relative gap-2 h-10 w.full ${showPanel ? 'display-block' : 'hidden'} transition-opacity duration-300 `}
            >
                <div className="flex flex-row items-center justify-center w-full gap-2">
                    <Slider
                        defaultValue={[100]}
                        max={100}
                        min={0}
                        step={1}
                        onValueChange={([val]) => onOpacityChange(val / 100)}
                        className="min-w-[100px] hover:cursor-pointer"
                    />
                    <p className="text-xs text-center mt-1 opacity-80 whitespace-nowrap">Thermal Opacity</p>
                </div>
            </div>
        </div>
    );
}
