import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { Group, Report } from "@/types";
import { useState } from "react";
import { Edit, Trash2, Plus, ChevronUp, ChevronDown } from "lucide-react"
import { motion, AnimatePresence } from "motion/react";
import { ReportTable } from "@/components/overview/ReportTable";

interface Props {
  group: Group;
  handleAddReport: (groupId: number, groupName: string) => void;
}

export function GroupCard({ group, handleAddReport }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);
  if (!group) {
    return <div className="text-red-500">Group not found</div>;
  }

  const openGroupReport = (e: React.MouseEvent) => {
    console.log(e);
    e.stopPropagation();
    // link to group report page with react
    window.location.href = `/group/${group.id}`;
  }

  return (
    <div className="group">
    <Card className="w-full mb-4" onClick={() => setIsExpanded(!isExpanded)}>
      <CardHeader>
        <div className="flex justify-between items-start w-full">
          {/* Left: Name & description */}
          <div className="space-y-1">
            <CardTitle className="text-xl">{group.name}</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              {group.description}
            </CardDescription>
          </div>

          {/* Right: Created date & report count */}
          <div className="text-right text-sm text-muted-foreground">
            <p>{new Date(group.created_at).toLocaleDateString()}</p>
            <p>
              {group.reports.length} report{group.reports.length !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
      </CardHeader>


    <AnimatePresence initial={false}>
    {isExpanded && (
      <motion.div
          key="expand"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.3, ease: "easeInOut" }}
          className="overflow-hidden"
        >
        <div className="flex px-6 pb-6 " >
          <Button variant="outline" className="" onClick={(e) => openGroupReport(e)}>
            Group Report
          </Button>
          
          <Button variant="outline" className="ml-2" onClick={(e) => { e.stopPropagation(); alert(`Editing group ${group.id}`); }}>
            <Edit className="" />  
          </Button>
          <Button variant="destructive" className="ml-2" onClick={(e) => { e.stopPropagation(); confirm(`Deleting group ${group.id}`); }}>
            <Trash2 className="" />
          </Button>
        </div>

        <Separator/>
        <CardContent className="px-6 py-4 space-y-3">
          <div className="flex items-center space-x-2">
            <h3 className="text-lg font-semibold">Reports</h3>
            <Button variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); handleAddReport(group.id, group.name); }}>
              <Plus className="mr-2" />
              Add Report
            </Button>
          </div>
          <div onClick={(e) => { e.preventDefault(); }} className="space-y-2">
            {group.reports.length > 0 ? (
              <ReportTable reports={group.reports} />
            ) : (
              <p className="text-sm text-muted-foreground">No reports available</p>
            )}
          </div>
        </CardContent>
      </motion.div>
    )}
    </AnimatePresence>
      <CardFooter className="">
        <div className="flex-1"></div>
        
        <Button
          variant="outline"
          className="ml-2 group-hover:bg-primary/90 group-hover:text-white transition-colors"
          onClick={(e) => { e.stopPropagation(); setIsExpanded(!isExpanded); }}
        >
          {isExpanded ? <ChevronUp /> : <ChevronDown />}
        </Button>
      </CardFooter>
    </Card>
    </div>
  );
}
