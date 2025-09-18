import * as React from "react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils" // shadcn helper for class merging

type ComboButtonOption = {
  key: string
  label: string
}

type ComboButtonProps = {
  /** currently selected key */
  value: string
  /** list of available options */
  options: ComboButtonOption[]
  /** fires when user selects a new option */
  onChange: (key: string) => void
  /** fires when user clicks the main button area */
  onAction: (key: string) => void
  /** extra tailwind classes */
  className?: string
}

/**
 * A Shadcn-styled combobutton: one button with a narrow dropdown section on the right.
 */
export const ComboButton: React.FC<ComboButtonProps> = ({
  value,
  options,
  onChange,
  onAction,
  className,
}) => {
  const selected = options.find((o) => o.key === value)

  return (
    <div
      className={cn(
        "inline-flex rounded-md shadow-sm border border-input bg-background",
        className
      )}
    >
      {/* Main action button */}
      <Button
        variant="default"
        className="rounded-r-none"
        onClick={() => onAction(value)}
      >
        {selected?.label}
      </Button>

      {/* Dropdown side */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="default"
            className="rounded-l-none px-2 border-l border-border flex items-center"
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {options.map((opt) => (
            <DropdownMenuItem key={opt.key} onClick={() => onChange(opt.key)}>
              {opt.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
