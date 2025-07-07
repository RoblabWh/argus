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
        className="relative p-2 flex flex-col justify-between items-center h-full gap-2"
    >

      {/* Delete Button */}
      {showDelete && onDelete && (
        <Button
          variant="secondary"
          size="icon"
          className="absolute top-3 right-3 rounded-full z-10 hover:bg-red-500 hover:text-white cursor-pointer"
          onClick={(e) => {
            e.stopPropagation(); // Prevents click from bubbling to Dropzone
            onDelete?.();
            }}
        >
          <X />
        </Button>
      )}

      {/* Image */}
        <div className="w-full overflow-hidden">
        <img
            src={src}
            alt={filename}
            className="w-full h-full object-contain"
        />
        </div>

        <div className="mt-2 w-full">
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
