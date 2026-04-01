import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import type { ReconstructionSettings } from "@/types/reconstruction";
import type { ReconstructionReport } from "@/types/report";

const PRESET_OPTIONS: {
  value: ReconstructionSettings["preset"];
  label: string;
  description: string;
}[] = [
  {
    value: "sparse",
    label: "Sparse (Fast)",
    description: "Trajectory + sparse point cloud only. Fastest option.",
  },
  {
    value: "dense_fast",
    label: "Dense — Fast (640×320)",
    description: "Adds a dense point cloud at 640×320 resolution. Slower.",
  },
  {
    value: "dense_detail",
    label: "Dense — Detail (1440×720)",
    description: "High-quality dense point cloud. Slow.",
  },
];

type Props = {
  status: string;
  progress?: number;
  isEditing?: boolean;
  onCancelEditing?: () => void;
  handleStartProcessing: (settings: ReconstructionSettings) => void;
  processButtonActive: boolean;
  existingSettings?: ReconstructionReport["processing_settings"];
};

export function ReconstructionSettingsCard({
  status,
  progress,
  isEditing,
  onCancelEditing,
  handleStartProcessing,
  processButtonActive,
  existingSettings,
}: Props) {
  const [preset, setPreset] = useState<ReconstructionSettings["preset"]>(
    existingSettings?.preset ?? "sparse"
  );
  const [frameStep, setFrameStep] = useState<number>(
    existingSettings?.frame_step ?? 5
  );

  const isActive =
    status === "queued" || status === "processing" || status === "running";

  const handleStart = () => {
    handleStartProcessing({
      preset,
      frame_step: frameStep,
      config_overrides: {},
    });
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">360° Reconstruction Settings</CardTitle>
      </CardHeader>

      <CardContent className="flex flex-col gap-5">
        {/* Preset selector */}
        <div className="flex flex-col gap-2">
          <Label className="text-sm font-medium">Processing preset</Label>
          <div className="flex flex-col gap-2">
            {PRESET_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                  preset === opt.value
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-muted/50"
                }`}
              >
                <input
                  type="radio"
                  name="preset"
                  value={opt.value}
                  checked={preset === opt.value}
                  onChange={() => setPreset(opt.value)}
                  className="mt-0.5 accent-primary"
                />
                <div>
                  <p className="text-sm font-medium leading-none">{opt.label}</p>
                  <p className="text-xs text-muted-foreground mt-1">{opt.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Frame step */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="frame-step" className="text-sm font-medium">
            Process every N frames
          </Label>
          <Input
            id="frame-step"
            type="number"
            min={1}
            max={30}
            value={frameStep}
            onChange={(e) => setFrameStep(Math.max(1, Math.min(30, Number(e.target.value))))}
            className="w-32"
          />
          <p className="text-xs text-muted-foreground">
            Higher = faster but fewer keyframes. Use 1 for maximum density.
          </p>
        </div>

        {/* Progress bar */}
        {isActive && progress !== undefined && (
          <div className="flex flex-col gap-1">
            <Progress value={progress} />
            <p className="text-xs text-muted-foreground">
              {status} — {Math.round(progress)}%
            </p>
          </div>
        )}
      </CardContent>

      <CardFooter className="flex gap-2 pt-0">
        <Button onClick={handleStart} disabled={processButtonActive}>
          {isEditing ? "Reprocess" : "Start Processing"}
        </Button>
        {isEditing && onCancelEditing && (
          <Button variant="outline" onClick={onCancelEditing}>
            Cancel
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
