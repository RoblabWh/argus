import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Report } from "@/types/report";
import { getApiUrl } from "@/api";
import { MapTab } from "./MapTab";

interface Props {
  report: Report;
}

export function TabArea({ report }: Props) {
  const api_url = getApiUrl();
  return (
    <Tabs
      defaultValue="mapping"
      className="w-full"
    >
      <div className="w-full flex justify-around items-center ">
        <TabsList className="">
          <TabsTrigger value="mapping">Map</TabsTrigger>
          <TabsTrigger value="slideshow">Images</TabsTrigger>
          <TabsTrigger value="data">Data</TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="mapping">
        <div className="text-sm mt-4 h-[calc(85vh)] overflow-auto">
          <MapTab report={report} />
        </div>
      </TabsContent>
      <TabsContent value="slideshow">
        <div className="p-4">
          {/* Placeholder for mapping content */}
          <p>Mapping content for report ID: {report.report_id}</p>
          <div className="text-sm text-muted-foreground mt-4 h-[calc(85vh)] overflow-auto">
            {/* show every image under report.mapping_report.maps */}
            {report.mapping_report?.maps.map((map, index) => (
              <div key={index} className="mb-2">
                <img src={api_url + '/' + map.url} alt={`Map ${index + 1}`} className="w-full h-auto" />
              </div>
            ))}
          </div>
        </div>
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