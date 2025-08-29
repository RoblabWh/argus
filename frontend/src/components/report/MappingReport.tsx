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
import { DetectionCard } from './mapingReportComponents/DetectionCard';

import {ResponsiveResizableLayout} from "@/components/ResponsiveResizableLayout";
import { Card, CardContent, CardTitle } from "@/components/ui/card";

function initiateThresholds(report: Report) {
    let images = report.mapping_report?.images || [];
    let thresholds: { [key: string]: number } = {};

    images.forEach((image) => {
        image.detections.forEach((detection) => {
            if (!(detection.class_name in thresholds)) {
                thresholds[detection.class_name] = 0.4; // Default threshold
            }
        });
    });
    return thresholds;
}

function initiateCategoryVisibility(report: Report) {
    let images = report.mapping_report?.images || [];
    let visibility: { [key: string]: boolean } = {};

    images.forEach((image) => {
        image.detections.forEach((detection) => {
            if (!(detection.class_name in visibility)) {
                visibility[detection.class_name] = true; // Default to visible
            }
        });
    });
    return visibility;
}



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
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState("map");
  const { data: webODMData } = useWebODM();
  const [thresholds, setThresholds] = useState<{ [key: string]: number }>({
    ...initiateThresholds(report),
  });
  const [visibleCategories, setVisibleCategories] = useState<{ [key: string]: boolean }>({
    ...initiateCategoryVisibility(report),
  });

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
              <DetectionCard report={report} setThresholds={setThresholds} thresholds={thresholds} setSearch={setSearch} visibleCategories={visibleCategories} setVisibleCategories={setVisibleCategories} />
            </div>
            <GalleryCard images={report.mapping_report?.images} setFilteredImages={setFilteredImages} filteredImages={filteredImages} setSelectedImage={selectImageFromGallery} search={search} setSearch={setSearch} />
            {/* Add more cards as needed */}
          </div>
        }
        right={
          <TabArea report={report} filteredImages={filteredImages} selectedImage={selectedImage} setSelectedImage={setSelectedImage} tab={tab} setTab={setTab} thresholds={thresholds} visibleCategories={visibleCategories}/>
        }
      />
    </>
  );
}
