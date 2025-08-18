import { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import type { Report } from '@/types/report';
import type { ReportSummary } from '@/types/report';
import { DetailedReportTable } from './DetailedReportTable';
import { GroupMapTab } from './GroupMapTab';

interface Props {
    summaryReports: ReportSummary[];
}

export function GroupTabArea({ summaryReports }: Props) {
    const [activeTab, setActiveTab] = useState<string>("map");

    const onTabChange = (value: string) => {
        setActiveTab(value);
    }

    return (
        <Tabs
            onValueChange={onTabChange}
            value={activeTab}
            className="w-full relative h-full "
        >
            <div className="absolute left-[50%] -translate-x-[50%] top-2 z-4">
                <TabsList className="">
                    <TabsTrigger value="map">Map</TabsTrigger>
                    <TabsTrigger value="reports">Reports</TabsTrigger>
                    <TabsTrigger value="data">Data</TabsTrigger>
                </TabsList>
            </div>

            <TabsContent value="map">
                <div className="relative text-sm h-[calc(100%)] overflow-auto z-0">
                    {/* <MapTab report={report} selectImageOnMap={selectImageOnMap} /> */}
                    <GroupMapTab summaryReports={summaryReports} />
                </div>
            </TabsContent>

            <TabsContent value="reports">
                <div className="w-full overflow-auto max-h-[calc(100vh-80px)]">
                    <DetailedReportTable reports={summaryReports} />
                </div>
            </TabsContent>

            <TabsContent value="data">
                <div className="text-sm text-muted-foreground mt-4 overflow-auto max-h-[calc(100vh-200px)]">
                    {/* Print every property of the report object */}
                    <pre>{JSON.stringify(summaryReports, null, 2)}</pre>
                </div>
            </TabsContent>
        </Tabs>
    );
}