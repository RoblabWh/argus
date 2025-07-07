import React from 'react';
import type { Report } from '@/types/report';
import { Button } from '../ui/button';

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
          <h3>Processing...</h3>
          <div className="relative pt-1">
            <div className="flex mb-2 items-center justify-between">
              <div>
                <span className="text-xs text-muted-foreground">Progress</span>
              </div>
              <div className="text-xs font-medium">{progress}%</div>
            </div>
            <div className="h-2 bg-muted">
              <div
                className="h-2 bg-blue-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </div>
      )}

      <Button variant="outline" className="mt-4" onClick={onEditClicked}>
        Edit
      </Button>

      <div className="text-sm text-muted-foreground mt-4">
        {/* Print every property of the report object */}
          <pre>{JSON.stringify(report, null, 2)}</pre>
          </div>
          
        </div>
  );
}
