import React from 'react';
import type { Report } from '@/types/report';
import { UploadArea } from '@/components/report/UploadArea';
import { useLocation } from 'react-router-dom';
interface Props {
    report: Report;
}
export function Upload({ report }: Props) {
  console.log("Upload component rendered with report:", report);
  let location = useLocation();
  console.log(location);
  return (
    <div className="w-full bg-blue-50">
      <h2>Upload Report</h2>
      <div>Current URL is {location.pathname}</div>;
      <UploadArea report={report} />
      
      {/* Print every property of the report object */}
      <pre>{JSON.stringify(report, null, 2)}</pre>
      {/* Upload form goes here */}
    </div>
  );
}
