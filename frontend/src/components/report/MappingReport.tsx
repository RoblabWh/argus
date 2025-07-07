import React from 'react';
import type { Report } from '@/types/report';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress'; // From shadcn

interface Props {
  report: Report;
  onEditClicked: () => void;
}

export function MappingReport({ report, onEditClicked }: Props) {
  // if the status is processing, we can show a progress bar
  const isProcessing = report.status === 'processing' || report.status === 'completed';
  const progress = report.progress ? Math.round(report.progress) : 0;
  
  
  return (
    <div className="w-full ">
      <h2>Upload Report</h2>
      <div>Current URL is {location.pathname}</div>

      {isProcessing && (
        <div className="mt-4">
          <div className="relative pt-1">

            </div>
            {((report.status === "processing") && report.progress !== undefined) && (
              <div>
                <Progress value={report.progress} />
                <p className="text-sm text-muted-foreground mt-1">
                  {report.status} — {Math.round(report.progress)}%
                </p>
              </div>
            )}

          </div>
      )}

      {report.status === 'completed' && (
      <Button variant="outline" className="mt-4" onClick={onEditClicked}>
        Edit
      </Button>
      )}
      

      <div className="text-sm text-muted-foreground mt-4">
        {/* Print every property of the report object */}
          <pre>{JSON.stringify(report, null, 2)}</pre>
          </div>
          
        </div>
  );
}
