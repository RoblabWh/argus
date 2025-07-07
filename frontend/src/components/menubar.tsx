import React from "react";
// import Link from "next/link";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Menu } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import { ModeToggle } from "./ui/mode-toggle";



// interface TopMenuBarProps {
//   breadcrumbs: { label: string; href: string }[];
// }

const TopMenuBar: React.FC = () => {
  const { breadcrumbs } = useBreadcrumbs();
  
  return (
    <div className="w-full flex justify-between items-center p-4 pb-2 pt-2 border-b  shadow-sm">
      <div className="flex items-center gap-4">
       <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="flex items-center gap-2">
             <Menu className="w-4 h-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <Link to="/settings">Settings</Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link to="/about">About</Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link to="/overview">Overview</Link>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/">Home</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          {breadcrumbs.map((crumb, index) => (
            <React.Fragment key={index}>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  {crumb.href ? <Link to={crumb.href}>{crumb.label}</Link> : crumb.label}
                </BreadcrumbLink>
              </BreadcrumbItem>
            </React.Fragment>
          ))}
        </BreadcrumbList>
      </Breadcrumb>
      </div>

      <ModeToggle />

     
    </div>
  );
};

export default TopMenuBar;
