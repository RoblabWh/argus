import React, { useState, useEffect } from 'react';
import { useGroups } from '@/hooks/groupHooks';
import { useBreadcrumbs } from '@/contexts/BreadcrumbContext';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';
import { GroupCard } from '@/components/overview/GroupCard';
import { NewGroupPopup } from '@/components/overview/NewGroupPopup';
import { NewReportPopup } from '@/components/overview/NewReportPopup';

export default function Overview() {
  const { setBreadcrumbs } = useBreadcrumbs();
  useEffect(() => {
    setBreadcrumbs([{ label: "Overview", href: "/overview" }]);
  }, []);

  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [isNewGroupOpen, setIsNewGroupOpen] = useState(false)
  const [isNewReportOpen, setIsNewReportOpen] = useState(false);
  const { data: groups, isLoading, error } = useGroups();

  if (isLoading) return <p>Loading...</p>;
  if (error) return <p>Error loading groups</p>;
  if (!groups || groups.length === 0) return <p>No groups found yet</p>;

  const handleAddReport = (groupId: number, groupName: string) => {
    setSelectedGroupId(groupId);
    setIsNewReportOpen(true);
  };



  // setBreadcrumbs([{ label: "Overview", href: "/overview" }]);


  return (
    <div className="p-6 mx-auto min-w-800px max-w-2/3">
      <div className="flex">
        <h1 className="text-2xl font-bold mb-4 mr-2">Flight Report Overview</h1>
        <Button variant="outline" size="sm" onClick={() => setIsNewGroupOpen(true)}>
          <Plus className="mr-2" />
          New Group
        </Button>
      </div>

      {groups.map((group) => (
        <GroupCard key={group.id} group={group} handleAddReport={handleAddReport} />
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

    </div>
  )
}
