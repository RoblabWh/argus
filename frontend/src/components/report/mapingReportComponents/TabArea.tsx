import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@/components/ui/accordion";
import type { Report } from "@/types/report";
import type { Image, ImageBasic } from "@/types/image";
import { getApiUrl } from "@/api";
import { MapTab } from "./MapTab";
import { SlideshowTab } from "@/components/report/mapingReportComponents/SlidehowTab";
import { useImages } from "@/hooks/imageHooks";

interface Props {
  report: Report;
  filteredImages?: ImageBasic[];
  selectedImage: ImageBasic | null;
  setSelectedImage: (image: ImageBasic | null) => void;
  tab: string;
  setTab: (value: string) => void;
  thresholds: { [key: string]: number };
  visibleCategories: { [key: string]: boolean };
}

export function TabArea({ report, filteredImages, selectedImage, setSelectedImage, tab, setTab, thresholds, visibleCategories }: Props) {
  const api_url = getApiUrl();
  const { data: images } = useImages(report.report_id);

  const onTabChange = (value: string) => {
    setTab(value);
  }


  const selectImageOnMap = (image_id: number) => {
    setSelectedImage(images?.find(img => img.id === image_id) || null);
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
    if (images && images.length > 0) {
      setSelectedImage(images[0]);
    }
  }, [images]);

  return (
    <Tabs
      onValueChange={onTabChange}
      value={tab}
      className="w-full relative h-full "
    >
      <div className="absolute left-[50%] -translate-x-[50%] top-2 z-10">
        <TabsList className="">
          <TabsTrigger className="cursor-pointer" value="map">Map</TabsTrigger>
          <TabsTrigger className="cursor-pointer" value="slideshow">Images</TabsTrigger>
          <TabsTrigger className="cursor-pointer" value="data">Data</TabsTrigger>
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
          nextImage={() => changeImage('next')}
          previousImage={() => changeImage('previous')}
          thresholds={thresholds}
          visibleCategories={visibleCategories}
          report_id={report.report_id}
        />
      </TabsContent>
      <TabsContent value="data">
        {/* Data content goes here */}
        <div className="text-sm text-muted-foreground mt-4 h-[calc(85vh)] overflow-auto">
          <Accordion type="single" collapsible className="mt-4">
            <AccordionItem value="item-1">
              <AccordionTrigger>Report Data</AccordionTrigger>
              <AccordionContent>
                <pre>{JSON.stringify(report, null, 2)}</pre>
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-2">
              <AccordionTrigger>Images Data</AccordionTrigger>
              <AccordionContent>
                <pre>{JSON.stringify(images, null, 2)}</pre>
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-3">
              <AccordionTrigger>Detections</AccordionTrigger>
              <AccordionContent>
                <p>TODO</p>
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-4">
              <AccordionTrigger>Maps</AccordionTrigger>
              <AccordionContent>
                <p>TODO</p>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </TabsContent>
    </Tabs>
  );
}