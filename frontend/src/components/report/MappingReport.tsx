import { use, useEffect, useState } from 'react';
import type { Report } from '@/types/report';
import type { Image } from '@/types/image';
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
import { useWebODM } from '@/hooks/useWebODM';

import ResponsiveResizableLayout from "@/components/report/mapingReportComponents/MappingReportLayout";
import { Card, CardContent, CardTitle } from "@/components/ui/card";


interface Props {
  report: Report;
  onEditClicked: () => void;
}

export function MappingReport({ report, onEditClicked }: Props) {
  // if the status is processing, we can show a progress bar
  const isProcessing = report.status === 'processing' || report.status === 'completed';
  const progress = report.progress ? Math.round(report.progress) : 0;
  const [filteredImages, setFilteredImages] = useState<Image[]>([]);
  const [selectedImage, setSelectedImage] = useState<Image | null>(null);
  const [tab, setTab] = useState("map");
  const { data: webODMData } = useWebODM();

  const selectImageFromGallery = (image: Image | null) => {
    setSelectedImage(image);
    setTab("slideshow");
  };

  console.log("webODMData:", webODMData);
  

  
    useEffect(() => {
      let sorted_images = report.mapping_report?.images || [];
      //sort by created_at descending
      sorted_images = sorted_images.sort((a, b) =>  new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
      //filter
      if (report.mapping_report?.images && report.mapping_report.images.length > 0) {
        setFilteredImages(report.mapping_report.images);
      }
    }, [report.mapping_report?.images]);


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
              <WebOdmCard isWebODMAvailable={webODMData?.is_available} webODMURL={webODMData?.url} webODMProjectID={report.mapping_report?.webodm_project_id} reportID={report.report_id} progress={report.progress} />
            </div>
            <GalleryCard images={report.mapping_report?.images} setFilteredImages={setFilteredImages} filteredImages={filteredImages} setSelectedImage={selectImageFromGallery} />
            {/* Add more cards as needed */}
          </div>
        }
        right={
          <TabArea report={report} filteredImages={filteredImages} selectedImage={selectedImage} setSelectedImage={setSelectedImage} tab={tab} setTab={setTab} />
        }
      />
    </>
  );
}
