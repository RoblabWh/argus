import React, { useState, useEffect } from 'react';
import { useGroups } from '@/hooks/groupHooks';
import { useBreadcrumbs } from '@/contexts/BreadcrumbContext';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';
import { GroupCard } from '@/components/overview/GroupCard';
import { NewGroupPopup } from '@/components/overview/NewGroupPopup';
import { NewReportPopup } from '@/components/overview/NewReportPopup';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowDown, ArrowUp } from "lucide-react";
import type { Group } from '@/types/group';
import { EditGroupPopup } from '@/components/group/EditGroupPopup';

export default function Overview() {
  const { setBreadcrumbs } = useBreadcrumbs();
  useEffect(() => {
    setBreadcrumbs([{ label: "Overview", href: "/overview" }]);
  }, []);

  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [isNewGroupOpen, setIsNewGroupOpen] = useState(false)
  const [isNewReportOpen, setIsNewReportOpen] = useState(false);
  const [isEditGroupOpen, setIsEditGroupOpen] = useState(false);
  const [showRawData, setShowRawData] = useState(false);
  const { data: groups, isLoading, error } = useGroups();
  const [sortBy, setSortBy] = useState<"created_at" | "name" | "id">("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");



  if (isLoading) return <p>Loading...</p>;
  if (error) return <p>Error loading groups</p>;
  if (!groups) return <p>No groups found yet</p>;

  const sortedGroups = [...groups].sort((a, b) => {
    const aVal = a[sortBy];
    const bVal = b[sortBy];

    if (typeof aVal === "string" && typeof bVal === "string") {
      return sortOrder === "asc"
        ? aVal.localeCompare(bVal)
        : bVal.localeCompare(aVal);
    }

    if (typeof aVal === "number" && typeof bVal === "number") {
      return sortOrder === "asc" ? aVal - bVal : bVal - aVal;
    }

    return 0;
  });

  const handleAddReport = (groupId: number, groupName: string) => {
    setSelectedGroupId(groupId);
    setIsNewReportOpen(true);
  };

  const onEditGroupDetailsClick = (groupId: number) => {
    setSelectedGroupId(groupId);
    setIsEditGroupOpen(true);
  };



  // setBreadcrumbs([{ label: "Overview", href: "/overview" }]);


  return (
    <div className="container mx-auto px-4 pt-4">
      <div className="flex">
        <h1 className="text-2xl font-bold mb-4 mr-2">Flight Report Overview</h1>
        <Button variant="outline" size="sm" onClick={() => setIsNewGroupOpen(true)}>
          <Plus className="mr-2" />
          New Group
        </Button>
      </div>

      <div className="flex items-center justify-end gap-0 mb-4">

        <Button
          variant="ghost"
          size="icon"
          onClick={() => setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"))}
        >
          {sortOrder === "asc" ? <ArrowUp className="h-5 w-5" /> : <ArrowDown className="h-5 w-5" />}

        </Button>

        <Select value={sortBy} onValueChange={(val) => setSortBy(val as any)}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="created_at">Date (creation)</SelectItem>
            <SelectItem value="name">Name</SelectItem>
            <SelectItem value="id">ID</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {sortedGroups.map((group) => (
        <GroupCard key={group.id} group={group} handleAddReport={handleAddReport} handleEditGroup={onEditGroupDetailsClick} />
      ))}

      <NewGroupPopup open={isNewGroupOpen} onOpenChange={setIsNewGroupOpen} />
      {selectedGroupId !== null && (
        <NewReportPopup
          open={isNewReportOpen}
          onOpenChange={setIsNewReportOpen}
          groupId={selectedGroupId}
          groupName={groups.find(g => g.id === selectedGroupId)?.name || ""}
        />
      )}

      <Button variant="outline" size="sm" className="mt-4" onClick={() => setShowRawData(!showRawData)}>
        {showRawData ? "Hide Raw Data" : "Show Raw Data"}
      </Button>
      {showRawData && (
        <div className="text-sm text-muted-foreground mt-4">
          {/* Print every property of the report object */}
          <pre>{JSON.stringify(groups, null, 2)}</pre>
        </div>
      )}

      {selectedGroupId && (
        <EditGroupPopup
          open={isEditGroupOpen}
          onOpenChange={setIsEditGroupOpen}
          groupId={selectedGroupId}
          initialName={groups.find(g => g.id === selectedGroupId)?.name || ""}
          initialDescription={groups.find(g => g.id === selectedGroupId)?.description || ""}
        />
      )}

    </div>
  )
}
