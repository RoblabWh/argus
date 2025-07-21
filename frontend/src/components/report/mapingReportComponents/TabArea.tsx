import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Report } from "@/types/report";
import { getApiUrl } from "@/api";
import { MapTab } from "./MapTab";
import { SlideshowTab } from "@/components/report/mapingReportComponents/SlidehowTab";

interface Props {
  report: Report;
}

export function TabArea({ report }: Props) {
  const [selectedImage, setSelectedImage] = useState<Image | null>(null);

  const api_url = getApiUrl();
  
  const selectImageOnMap = (image: Image) => {
    setSelectedImage(image);
  }

  const changeImage = (direction: 'next' | 'previous') => {
    if (!report.mapping_report?.images || report.mapping_report.images.length === 0) return;
    const currentIndex = report.mapping_report.images.findIndex(img => img.url === selectedImage?.url);
    if (currentIndex === -1) return;

    const newIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1;
    if (newIndex < 0)
      setSelectedImage(report.mapping_report.images[report.mapping_report.images.length - 1]);
    else if (newIndex >= report.mapping_report.images.length)
      setSelectedImage(report.mapping_report.images[0]);
    else 
      setSelectedImage(report.mapping_report.images[newIndex]);
  }

  useEffect(() => {
    if (report.mapping_report?.images && report.mapping_report.images.length > 0) {
      setSelectedImage(report.mapping_report.images[0]);
    }
  }, [report.mapping_report?.images]);

  return (
    <Tabs
      defaultValue="mapping"
      className="w-full relative h-full "
    >
      <div className="absolute left-[50%] -translate-x-[50%] top-2 z-10">
        <TabsList className="">
          <TabsTrigger value="mapping">Map</TabsTrigger>
          <TabsTrigger value="slideshow">Images</TabsTrigger>
          <TabsTrigger value="data">Data</TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="mapping">
        <div className="text-sm h-[calc(100%)] overflow-auto">
          <MapTab report={report} />
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