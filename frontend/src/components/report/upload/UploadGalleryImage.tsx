import React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { X } from "lucide-react";

type Props = {
  src: string;
  filename?: string;
  onDelete?: () => void;
  showDelete?: boolean;
  children?: React.ReactNode; // for progress bar or extras
};

export const GalleryImage: React.FC<Props> = ({
  src,
  filename,
  onDelete,
  showDelete = true,
  children,
}) => {
  return (
    <Card 
        className="relative p-0 flex flex-col justify-between items-center h-full gap-0 rounded-sm"
    >

      {/* Delete Button */}
      {showDelete && onDelete && (
        <Button
          variant="secondary"
          size="icon"
          className="absolute top-2 right-3 rounded-full z-10 hover:bg-red-500 hover:text-white cursor-pointer"
          onClick={(e) => {
            e.stopPropagation(); // Prevents click from bubbling to Dropzone
            onDelete?.();
            }}
        >
          <X />
        </Button>
      )}

      {/* Image */}
        <div className="w-full overflow-hidden p-1">
        <img
            src={src}
            alt={filename}
            className="w-full h-full object-contain rounded-xs"
        />
        </div>

        <div className="mt-0 w-full p-2">
            {children} {/* typically the Progress */}
            {filename && (
            <Tooltip>
                <TooltipTrigger asChild>
                <p className="text-sm mt-1 w-full truncate text-center">{filename}</p>
                </TooltipTrigger>
                <TooltipContent>
                <p>{filename}</p>
                </TooltipContent>
            </Tooltip>
            )}
        </div>
    </Card>
  );
};
