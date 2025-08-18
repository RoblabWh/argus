import { use, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useBreadcrumbs } from '@/contexts/BreadcrumbContext';
import { useGroup } from '@/hooks/groupHooks';
import { useSummaryReports } from '@/hooks/useSummaryReports';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardTitle } from '@/components/ui/card';
import { ResponsiveResizableLayout } from '@/components/ResponsiveResizableLayout';
import { GroupTabArea } from '@/components/group/GroupTabArea';
import type { Group } from '@/types/group';
import { GeneralDataCard } from '@/components/group/GenerealGroupDataCard';
import { FlightGroupCard } from '@/components/group/FlightGroupCard';

export default function Group() {
    const { id } = useParams<{ id: string }>();
    const { setBreadcrumbs } = useBreadcrumbs();
    const { data: group, isLoading, error } = useGroup(Number(id));
    const { data: summaryReports } = useSummaryReports(Number(id));
    const [showRawData, setShowRawData] = useState(false);

    useEffect(() => {
        setBreadcrumbs([
            { label: "Overview", href: "/overview" },
            { label: "Group", href: `/group/${id}` }]);
    }, []);

    useEffect(() => {
        if (group) {
            setBreadcrumbs([
                { label: "Overview", href: "/overview" },
                { label: group.name, href: `/group/${group.id}` },
            ]);
        }
    }, [group]);

    if (isLoading) return <div>Loading...</div>;
    if (error) return <div>Error loading group</div>;
    if (!group) return <div>Group not found</div>;



    return (
        <div className="w-full h-[calc(100vh-54px)] overflow-hidden">

            <ResponsiveResizableLayout
                left={

                    <div className="flex flex-col gap-4 h-full w-full">
                        <div className='flex flex-wrap gap-4 w-full'>
                            <GeneralDataCard group={group} />
                            <FlightGroupCard data={summaryReports} />

                        </div>
                        {/* Add more cards as needed */}
                    </div>
                }
                right={
                    <GroupTabArea summaryReports={summaryReports} />
                }
            />
        </div>
    )

}
