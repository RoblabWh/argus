import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { Group, Report } from "@/types";
import { ReportItem } from "@/components/overview/ReportItem";
import { useState } from "react";
import { Edit, Trash2, Plus, ChevronUp, ChevronDown } from "lucide-react"
import { motion, AnimatePresence } from "motion/react";


interface Props {
  group: Group;
  handleAddReport: (groupId: number, groupName: string) => void;
}

export function GroupCard({ group, handleAddReport }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);
  if (!group) {
    return <div className="text-red-500">Group not found</div>;
  }

  return (
    <Card className="w-full mb-4">
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
        <div className="flex px-6 pb-6">
          <Button variant="outline" className="" onClick={() => alert(`Opening report for group ${group.id}`)}>
            Group Report
          </Button>
          
          <Button variant="outline" className="ml-2" onClick={() => alert(`Editing group ${group.id}`)}>
            <Edit className="" />  
          </Button>
          <Button variant="destructive" className="ml-2" onClick={() => confirm(`Deleting group ${group.id}`)}>
            <Trash2 className="" />
          </Button>
        </div>

        <Separator/>
        <CardContent className="px-6 py-4 space-y-3">
          <div className="flex items-center space-x-2">
            <h3 className="text-lg font-semibold">Reports</h3>
            <Button variant="outline" size="sm" onClick={() => handleAddReport(group.id, group.name)}>
              <Plus className="mr-2" />
              Add Report
            </Button>
          </div>
  
          {group.reports.length > 0 ? (
            group.reports.map((report: Report) => (
              <ReportItem key={report.report_id} report={report} />
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No reports available</p>
          )}
        </CardContent>
      </motion.div>
    )}
    </AnimatePresence>
      <CardFooter className="">
        <div className="flex-1"></div>
        
        
        <Button variant="default" className="ml-2" onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? <ChevronUp /> : <ChevronDown />}
        </Button>
      </CardFooter>
    </Card>
  );
}
