import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@/components/ui/accordion";
import { useImages } from "@/hooks/imageHooks";
import { useMaps } from "@/hooks/useMaps";
import type { Report } from "@/types/report";
import { useDetections } from "@/hooks/detectionHooks";


interface props {
    report: Report;
}

export function DataTab({ report }: props) {
    const reportID = report.report_id;
    const { data: images, isLoading: isLoadingImages, isError: isErrorImages } = useImages(reportID);
    const { data: detections, isLoading: isLoadingDetections, isError: isErrorDetections } = useDetections(reportID);
    const { data: maps, isLoading: isLoadingMaps, isError: isErrorMaps } = useMaps(reportID); // Placeholder for maps data

    return (
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
                        {isLoadingImages ? (
                            <div>Loading...</div>
                        ) : isErrorImages ? (
                            <div>Error loading images.</div>
                        ) : (
                            <pre>{JSON.stringify(images, null, 2)}</pre>
                        )}
                    </AccordionContent>
                </AccordionItem>
                <AccordionItem value="item-3">
                    <AccordionTrigger>Detections</AccordionTrigger>
                    <AccordionContent>
                        {isLoadingDetections ? (
                            <div>Loading...</div>
                        ) : isErrorDetections ? (
                            <div>Error loading detections.</div>
                        ) : (
                            <pre>{JSON.stringify(detections, null, 2)}</pre>
                        )}
                    </AccordionContent>
                </AccordionItem>
                <AccordionItem value="item-4">
                    <AccordionTrigger>Maps</AccordionTrigger>
                    <AccordionContent>
                        {isLoadingMaps ? (
                            <div>Loading...</div>
                        ) : isErrorMaps ? (
                            <div>Error loading maps.</div>
                        ) : (
                            <pre>{JSON.stringify(maps, null, 2)}</pre>
                        )}
                    </AccordionContent>
                </AccordionItem>
            </Accordion>
        </div>
    );
}