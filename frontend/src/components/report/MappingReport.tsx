import { useEffect, useState } from 'react';
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
import { GalleryCard } from './mapingReportComponents/GalleryCard';
import { Toaster } from '@/components/ui/sonner';

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

  const selectImageFromGallery = (image: Image | null) => {
    setSelectedImage(image);
    setTab("slideshow");
  };
  

  
    useEffect(() => {
      let sorted_images = report.mapping_report?.images || [];
      //sort by created_at descending
      sorted_images = sorted_images.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
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
          <div className="flex flex-col gap-4 h-[calc(100vh-90px)]">
            <div className='flex flex-wrap gap-4'>
              <GeneralDataCard report={report} onReprocessClicked={onEditClicked} />
              <WeatherCard data={report.mapping_report?.weather[0]} onReload={() => { alert("Reload Weather Data"); }} />
              <FlightCard data={report.mapping_report} />
              <AutoDescriptionCard description={report.auto_description} />
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
