import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import type { Report } from "@/types/report";
import type { ReconstructionResults } from "@/types/reconstruction";

interface Props {
  report: Report;
  results: ReconstructionResults | undefined;
}

export function ReconstructionDataTab({ report, results }: Props) {
  return (
    <div className="text-sm text-muted-foreground mt-4 h-[calc(85vh)] overflow-auto">
      <Accordion type="single" collapsible className="mt-4">
        <AccordionItem value="report">
          <AccordionTrigger>Report Data</AccordionTrigger>
          <AccordionContent>
            <pre className="text-xs overflow-auto">{JSON.stringify(report, null, 2)}</pre>
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="results">
          <AccordionTrigger>Reconstruction Results</AccordionTrigger>
          <AccordionContent>
            {results == null ? (
              <p className="text-xs text-muted-foreground">Not yet available.</p>
            ) : (
              <pre className="text-xs overflow-auto">{JSON.stringify(results, null, 2)}</pre>
            )}
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
