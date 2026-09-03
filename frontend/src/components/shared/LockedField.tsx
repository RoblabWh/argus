import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Lock, Unlock } from "lucide-react";

/**
 * Deliberate-edit affordance: a value that was filled in for the user is shown disabled
 * behind a lock, so changing it takes an explicit click rather than a stray one.
 *
 * Originally local to the settings page (API keys, credentials); shared once the DRZ image
 * share dialog needed the same guard over an automatically read EXIF coordinate.
 */
export function LockButton({
  locked,
  onToggle,
  label = "field",
}: {
  locked: boolean;
  onToggle: () => void;
  /** Named in the aria-label, e.g. "position" -> "Unlock position". */
  label?: string;
}) {
  return (
    <Button
      variant="ghost"
      size="icon"
      type="button"
      aria-label={locked ? `Unlock ${label}` : `Lock ${label}`}
      onClick={onToggle}
    >
      {locked ? <Lock className="h-5 w-5" /> : <Unlock className="h-5 w-5" />}
    </Button>
  );
}

export function LockedField({
  id,
  label,
  type = 'text',
  value,
  onChange,
  locked,
  onToggleLock,
}: {
  id: string;
  label: string;
  type?: 'text' | 'password';
  value: string;
  onChange: (v: string) => void;
  locked: boolean;
  onToggleLock: () => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex items-center gap-2">
        <Input
          id={id}
          type={type}
          disabled={locked}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1"
        />
        <LockButton locked={locked} onToggle={onToggleLock} />
      </div>
    </div>
  );
}
