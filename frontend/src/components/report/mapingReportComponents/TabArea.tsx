import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Report } from "@/types/report";
import type { Image } from "@/types/image";
import { getApiUrl } from "@/api";
import { MapTab } from "./MapTab";
import { SlideshowTab } from "@/components/report/mapingReportComponents/SlidehowTab";

interface Props {
  report: Report;
  filteredImages?: Image[];
  selectedImage: Image | null;
  setSelectedImage: (image: Image | null) => void;
  tab: string;
  setTab: (value: string) => void;
}

export function TabArea({ report, filteredImages , selectedImage, setSelectedImage, tab, setTab }: Props) {
  const api_url = getApiUrl();

  const onTabChange = (value: string) => {
    setTab(value);
  }


  const selectImageOnMap = (image_id: number) => {
    setSelectedImage(report.mapping_report?.images?.find(img => img.id === image_id) || null);
    setTab("slideshow");
  }

  const changeImage = (direction: 'next' | 'previous') => {
    if (!filteredImages || filteredImages.length === 0) return;
    const currentIndex = filteredImages.findIndex(img => img.url === selectedImage?.url);
    if (currentIndex === -1) {
      //try finding the closest image in the selection
      // calc date time difference between selectedImage and each image in filteredImages
      const closestImage = filteredImages.reduce((prev, curr) => {
        const prevDate = new Date(prev.created_at);
        const currDate = new Date(curr.created_at);
        const selectedDate = new Date(selectedImage?.created_at || 0);
        const prevDiff = Math.abs(prevDate.getTime() - selectedDate.getTime());
        const currDiff = Math.abs(currDate.getTime() - selectedDate.getTime());
        return currDiff < prevDiff ? curr : prev;
      });
      setSelectedImage(closestImage);
      if (!closestImage) {
        setSelectedImage(filteredImages[0]);
        console.error("No closest image found");
        return;
      }
      
      return;
    }
    if (currentIndex === -1) return;

    const newIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1;
    if (newIndex < 0)
      setSelectedImage(filteredImages[filteredImages.length - 1]);
    else if (newIndex >= filteredImages.length)
      setSelectedImage(filteredImages[0]);
    else
      setSelectedImage(filteredImages[newIndex]);
  }

  useEffect(() => {
    if (report.mapping_report?.images && report.mapping_report.images.length > 0) {
      setSelectedImage(report.mapping_report.images[0]);
    }
  }, [report.mapping_report?.images]);

  return (
    <Tabs
      onValueChange={onTabChange}
      value={tab}
      className="w-full relative h-full "
    >
      <div className="absolute left-[50%] -translate-x-[50%] top-2 z-10">
        <TabsList className="">
          <TabsTrigger value="map">Map</TabsTrigger>
          <TabsTrigger value="slideshow">Images</TabsTrigger>
          <TabsTrigger value="data">Data</TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="map">
        <div className="text-sm h-[calc(100%)] overflow-auto">
          <MapTab report={report} selectImageOnMap={selectImageOnMap} />
        </div>
      </TabsContent>
      <TabsContent value="slideshow">
        <SlideshowTab
          selectedImage={selectedImage}
          images={report.mapping_report?.images || []}
          nextImage={() => changeImage('next')}
          previousImage={() => changeImage('previous')}
        />
      </TabsContent>
      <TabsContent value="data">
        {/* Data content goes here */}
        <div className="text-sm text-muted-foreground mt-4 h-[calc(85vh)] overflow-auto">
          {/* Print every property of the report object */}
          <pre>{JSON.stringify(report, null, 2)}</pre>
        </div>
      </TabsContent>
    </Tabs>
  );
}