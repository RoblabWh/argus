import { use, useEffect, useState } from 'react';
import type { Report } from '@/types/report';
import type { Image, ImageBasic } from '@/types/image';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress'; // From shadcn
import { GeneralDataCard } from './mapingReportComponents/GeneralDataCard';
import { DatabaseCard } from './mapingReportComponents/DatabaseCard';
import { TabArea } from './mapingReportComponents/TabArea';
import { WeatherCard } from './mapingReportComponents/WeatherCard';
import { FlightCard } from './mapingReportComponents/FlightCard';
import { AutoDescriptionCard } from './mapingReportComponents/AutoDescriptionCard';
import { WebOdmCard } from './mapingReportComponents/WebOdmCard';
import { GalleryCard } from './mapingReportComponents/GalleryCard';
import { Toaster } from '@/components/ui/sonner';
import { DetectionCard } from './mapingReportComponents/DetectionCard';
import { ResponsiveResizableLayout } from "@/components/ResponsiveResizableLayout";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { useWebODM } from '@/hooks/useWebODM';
import { useDetections, useIsDetectionRunning } from '@/hooks/detectionHooks';
import { set } from 'date-fns';





interface Props {
  report: Report;
  onEditClicked: () => void;
  setReport: (report: Report) => void;
}

export function MappingReport({ report, onEditClicked, setReport }: Props) {
  const isProcessing = report.status === 'processing' || report.status === 'completed';
  const progress = report.progress ? Math.round(report.progress) : 0;
  const [filteredImages, setFilteredImages] = useState<ImageBasic[]>([]);
  const [selectedImage, setSelectedImage] = useState<ImageBasic | null>(null);
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState("map");
  const { data: webODMData } = useWebODM();
  const { data: detections } = useDetections(report.report_id);
  const [thresholds, setThresholds] = useState<{ [key: string]: number }>({});
  const [visibleCategories, setVisibleCategories] = useState<{ [key: string]: boolean }>({});

  const selectImageFromGallery = (image: ImageBasic | null) => {
    setSelectedImage(image);
    setTab("slideshow");
  };

  console.log("webODMData:", webODMData);


  return (
    <>
      <Toaster />
      <ResponsiveResizableLayout
        left={
          <div className="flex flex-col gap-4 h-full">
            <div className='flex flex-wrap gap-4'>
              <GeneralDataCard report={report} onReprocessClicked={onEditClicked} />
              <WeatherCard data={report.mapping_report?.weather[0]} onReload={() => { alert("Reload Weather Data"); }} />
              <FlightCard data={report.mapping_report} />
              <AutoDescriptionCard description={report.auto_description} />
              <WebOdmCard isWebODMAvailable={webODMData?.is_available || false} webODMURL={webODMData?.url} webODMProjectID={report.mapping_report?.webodm_project_id} reportID={report.report_id} progress={report.progress} />
              <DetectionCard report_id={report.report_id} setThresholds={setThresholds} thresholds={thresholds} setSearch={setSearch} visibleCategories={visibleCategories} setVisibleCategories={setVisibleCategories} />
            </div>
            <GalleryCard reportId={report.report_id} setFilteredImages={setFilteredImages} filteredImages={filteredImages} setSelectedImage={selectImageFromGallery} search={search} setSearch={setSearch} />
          </div>
        }
        right={
          // <Card className="h-full">
          //   <CardContent className="h-full">
          //     <p>Selected Image: {selectedImage ? selectedImage.id : "None"}</p>
          //   </CardContent>
          // </Card>
          <TabArea report={report}  filteredImages={filteredImages} selectedImage={selectedImage} setSelectedImage={setSelectedImage} tab={tab} setTab={setTab} thresholds={thresholds} visibleCategories={visibleCategories}/>
        }
      />
    </>
  );
}
