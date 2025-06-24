import React from 'react';
import type { Report } from '@/types/report';

interface Props {
    report: Report;
}
export function Upload({ report }: Props) {
    console.log("Upload component rendered with report:", report);
  return (
    <div className="w-full bg-blue-50">
      <h2>Upload Report</h2>
      {/* Print every property of the report object */}
      <pre>{JSON.stringify(report, null, 2)}</pre>
      {/* Upload form goes here */}
    </div>
  );
}
