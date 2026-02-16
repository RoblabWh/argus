import { useState } from 'react';
import type { Report } from '@/types/report';
import type { Image, ImageBasic } from '@/types/image';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress'; // From shadcn
import { GeneralDataCard } from './mappingReportComponents/GeneralDataCard';
import { DatabaseCard } from './mappingReportComponents/DatabaseCard';
import { TabArea } from './mappingReportComponents/TabArea';
import { WeatherCard } from './mappingReportComponents/WeatherCard';
import { FlightCard } from './mappingReportComponents/FlightCard';
import { AutoDescriptionCard } from './mappingReportComponents/AutoDescriptionCard';
import { WebOdmCard } from './mappingReportComponents/WebOdmCard';
import { GalleryCard } from './mappingReportComponents/GalleryCardFiltered';
import { Toaster } from '@/components/ui/sonner';
import { DetectionCard } from './mappingReportComponents/DetectionCard';
import { ResponsiveResizableLayout } from "@/components/ResponsiveResizableLayout";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { useDetections, useIsDetectionRunning } from '@/hooks/detectionHooks';
import { FilteredImagesProvider } from '@/contexts/FileteredImagesContext';
import { useStopProcessing } from '@/hooks/useStartProcessing';



interface Props {
  report: Report;
  onEditClicked: () => void;
  setReport: (report: Report) => void;
}

export function MappingReport({ report, onEditClicked, setReport }: Props) {
  const [selectedImage, setSelectedImage] = useState<ImageBasic | null>(null);
  const [detectionFilter, setDetectionFilter] = useState<string[]>([]);
  const [tab, setTab] = useState("map");
  //const { data: detections } = useDetections(report.report_id);
  const [thresholds, setThresholds] = useState<{ [key: string]: number }>({});
  const [visibleCategories, setVisibleCategories] = useState<{ [key: string]: boolean }>({});
  const stopProcessingMutation = useStopProcessing(report.report_id);

  const handleStopProcessing = () => {
    stopProcessingMutation.mutate();
  };


  const selectImageFromGallery = (image: ImageBasic | null) => {
    setSelectedImage(image);
    setTab("slideshow");
  };



  return (
    <>
      <FilteredImagesProvider>
        <Toaster />
        <ResponsiveResizableLayout
          left={
            <div className="flex flex-col gap-4 h-full">
              <div className='flex flex-wrap gap-4'>
                <GeneralDataCard report={report} onReprocessClicked={onEditClicked} onStopProcessing={handleStopProcessing} />
                <WeatherCard data={report.mapping_report?.weather[0]} onReload={() => { alert("Reload Weather Data"); }} />
                <FlightCard data={report.mapping_report} />
                <AutoDescriptionCard reportID={report.report_id} description={report.auto_description} />
                <WebOdmCard webODMProjectID={report.mapping_report?.webodm_project_id} reportID={report.report_id} progress={report.progress} />
                <DetectionCard report_id={report.report_id} setThresholds={setThresholds} thresholds={thresholds} setFilter={setDetectionFilter} filters={detectionFilter} visibleCategories={visibleCategories} setVisibleCategories={setVisibleCategories} />
              </div>
              <GalleryCard reportId={report.report_id} setSelectedImage={selectImageFromGallery} detectionFilter={detectionFilter} setDetectionFilter={setDetectionFilter} thresholds={thresholds} />
            </div>
          }
          right={
            // <Card className="h-full">
            //   <CardContent className="h-full">
            //     <p>Selected Image: {selectedImage ? selectedImage.id : "None"}</p>
            //   </CardContent>
            // </Card>
            <TabArea report={report} selectedImage={selectedImage} setSelectedImage={setSelectedImage} tab={tab} setTab={setTab} thresholds={thresholds} visibleCategories={visibleCategories} />
          }
        />
      </FilteredImagesProvider>
    </>
  );
  
}
