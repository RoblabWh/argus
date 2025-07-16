import { motion, AnimatePresence } from "framer-motion";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { ReactNode } from "react";

type MappingTileProps = {
  title: string;
  icon: ReactNode;
  enabled: boolean;
  onToggle: (val: boolean) => void;
  children?: ReactNode;
};

export function MappingTile({
  title,
  icon,
  enabled,
  onToggle,
  children,
}: MappingTileProps) {
  const inactiveClasses =
    "cursor-pointer border border-muted-foreground/30 bg-muted/20 flex flex-col items-center justify-center hover:shadow-sm h-25 hover:border-primary";

  const tileBaseClasses =
    "border-2 border-primary p-4";

  return (
    <AnimatePresence mode="wait">

      <div
        className={cn(
          "relative transition-all duration-300 overflow-hidden rounded-2xl",
          enabled ? tileBaseClasses : inactiveClasses
        )}
        onClick={() => {
          if (!enabled) onToggle(true);
        }}
      >
        {enabled ? (
          <motion.div
            key="active"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
            className="space-y-4"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold pr-6">{title}</h3>
              <Switch checked={enabled} onCheckedChange={onToggle} className="cursor-pointer"/>
            </div>
            {children}
            <div className="absolute -bottom-8 left-2 opacity-10 z-0">{icon}</div>
          </motion.div>
        ) : (
          <motion.div
            key="inactive"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="w-full space-y-2 z-10 relative p-4 text-muted-foreground"
          >
            <div className="relative z-10 flex items-center justify-between gap-4">
              <h3 className="text-lg font-semibold">{title}</h3>
              <Switch checked={false} className="cursor-pointer" />
            </div>
            <p className="text-sm text-muted-foreground">Deactivated</p>
            <div className="absolute -bottom-6 left-2 opacity-20 z-0">{icon}</div>
            <div className="absolute inset-0 z-0 pointer-events-none bg-gradient-to-tl from-gray-200/90 via-gray-100/50 to-white/0 dark:from-gray-900/100 dark:via-gray-900/70 dark:to-gray-900/0" />
          </motion.div>
        )}
      </div>
    </AnimatePresence>

  );
}
