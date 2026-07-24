import { useEffect, useState, useCallback, lazy, Suspense } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Report } from "@/types/report";
import type { Image, ImageBasic } from "@/types/image";
import type { DetectionDisplayMode } from "@/types/detection";
import { getApiUrl } from "@/api";
import { MapTab } from "@/components/report/mappingReportComponents/MapTab";
import type { TempFilters } from "@/components/report/mappingReportComponents/GalleryCardFiltered";
import { SlideshowTab } from "@/components/report/mappingReportComponents/SlideshowTab";
import { DataTab } from "@/components/report/mappingReportComponents/DataTab";
import { useImages } from "@/hooks/imageHooks";
import { useFilteredImages } from "@/contexts/FileteredImagesContext";
import { usePollColmapStatus } from "@/hooks/usePollColmapStatus";
import { useColmapResults } from "@/hooks/useColmapResults";
import { useSseActive } from "@/hooks/useReportEvents";
import { Loader2 } from "lucide-react";

const ReconstructionPointcloudTab = lazy(() =>
  import("../reconstructionReportComponents/ReconstructionPointcloudTab").then(
    (m) => ({ default: m.ReconstructionPointcloudTab }),
  ),
);

interface Props {
  report: Report;
  selectedImage: ImageBasic | null;
  setSelectedImage: (image: ImageBasic | null) => void;
  tab: string;
  setTab: (value: string) => void;
  thresholds: { [key: string]: number };
  visibleCategories: { [key: string]: boolean };
  detectionMode: DetectionDisplayMode;
  setDetectionMode: (v: DetectionDisplayMode) => void;
  selectedObjectId: number | null;
  setSelectedObjectId: (id: number | null) => void;
  highlightedDetectionId: number | null;
  setHighlightedDetectionId: (id: number | null) => void;
  setRegionImageIds: (ids: number[] | null) => void;
  tempFilter: TempFilters;
}

export function TabArea({ report, selectedImage, setSelectedImage, tab, setTab, thresholds, visibleCategories, detectionMode, setDetectionMode, selectedObjectId, setSelectedObjectId, highlightedDetectionId, setHighlightedDetectionId, setRegionImageIds, tempFilter }: Props) {
  const api_url = getApiUrl();
  const { data: images } = useImages(report.report_id);
  const [visibleMapOverlays, setVisibleMapOverlays] = useState<{ [mapId: number]: boolean }>({});
  const { filteredImages, } = useFilteredImages();

  // COLMAP 3D reconstruction — shares the ["colmap-status", id] cache with
  // ColmapStatusIndicator; SSE flips has_reconstruction live once the worker finishes.
  const sseActive = useSseActive();
  const { data: colmapStatus } = usePollColmapStatus(report.report_id, true, sseActive);
  const hasColmap = !!colmapStatus?.has_reconstruction;
  const { data: colmapResults } = useColmapResults(report.report_id, hasColmap);

  const onTabChange = (value: string) => {
    setTab(value);
  }


  // const selectImageOnMap = (image_id: number) => {
  //   setSelectedImage(images?.find(img => img.id === image_id) || null);
  //   setTab("slideshow");
  // }
  const selectImageOnMap = useCallback((image_id: number) => {
    setSelectedImage(images?.find(img => img.id === image_id) || null);
    setTab("slideshow");
  }, [images, setSelectedImage, setTab]);


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
          {hasColmap && (
            <TabsTrigger className="cursor-pointer" value="pointcloud">3D</TabsTrigger>
          )}
        </TabsList>
      </div>
      {/* forceMount keeps the map alive when switching tabs, hidden with CSS */}
      <TabsContent value="map" forceMount className={tab !== "map" ? "hidden" : ""}>
        <div className="text-sm h-[calc(100%)] overflow-auto">
          <MapTab
            reportId={report.report_id}
            selectImageOnMap={selectImageOnMap}
            thresholds={thresholds}
            visibleCategories={visibleCategories}
            visibleMapOverlays={visibleMapOverlays}
            setVisibleMapOverlays={setVisibleMapOverlays}
            detectionMode={detectionMode}
            setDetectionMode={setDetectionMode}
            selectedObjectId={selectedObjectId}
            setSelectedObjectId={setSelectedObjectId}
            highlightedDetectionId={highlightedDetectionId}
            setHighlightedDetectionId={setHighlightedDetectionId}
            setRegionImageIds={setRegionImageIds}
            tempFilter={tempFilter}
          />
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
        <DataTab report={report} />
      </TabsContent>
      {/* COLMAP 3D tab — forceMount keeps the WebGL canvas alive when switching tabs */}
      {hasColmap && colmapResults?.sparse_pointcloud_url && (
        <TabsContent
          value="pointcloud"
          forceMount
          className={`h-full ${tab !== "pointcloud" ? "hidden" : ""}`}
        >
          <Suspense
            fallback={
              <div className="w-full h-full flex items-center justify-center text-muted-foreground gap-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="text-sm">Loading 3D viewer…</span>
              </div>
            }
          >
            <ReconstructionPointcloudTab results={colmapResults} apiUrl={api_url} sourceFrame="enu" />
          </Suspense>
        </TabsContent>
      )}
    </Tabs>
  );
}