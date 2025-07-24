import React, { createContext, useContext, useState } from "react";

type Crumb = { label: string; href?: string };

type BreadcrumbContextType = {
  breadcrumbs: Crumb[];
  setBreadcrumbs: (crumbs: Crumb[]) => void;
};

const BreadcrumbContext = createContext<BreadcrumbContextType | undefined>(undefined);

export const BreadcrumbProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [breadcrumbs, setBreadcrumbs] = useState<Crumb[]>([]);
  return (
    <BreadcrumbContext.Provider value={{ breadcrumbs, setBreadcrumbs }}>
      {children}
    </BreadcrumbContext.Provider>
  );
};

export const useBreadcrumbs = () => {
  const ctx = useContext(BreadcrumbContext);
  if (!ctx) throw new Error("useBreadcrumbs must be used within a BreadcrumbProvider");
  return ctx;
};
