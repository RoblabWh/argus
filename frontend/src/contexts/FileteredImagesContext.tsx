import React, { createContext, useContext, useState, useMemo } from "react";
import type { ImageBasic } from "@/types/image";

type FilteredImagesContextType = {
  filteredImages: ImageBasic[];
  setFilteredImages: (images: ImageBasic[]) => void;
};

const FilteredImagesContext = createContext<FilteredImagesContextType | undefined>(undefined);

export const FilteredImagesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [filteredImages, setFilteredImages] = useState<ImageBasic[]>([]);

  const value = useMemo(
    () => ({ filteredImages, setFilteredImages }),
    [filteredImages] // `setFilteredImages` is stable, so no need to include it
  );

  return (
    <FilteredImagesContext.Provider value={value}>
      {children}
    </FilteredImagesContext.Provider>
  );
};

export const useFilteredImages = () => {
  const ctx = useContext(FilteredImagesContext);
  if (!ctx) {
    throw new Error("useFilteredImages must be used within a FilteredImagesProvider");
  }
  return ctx;
};
