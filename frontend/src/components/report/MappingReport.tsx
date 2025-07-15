import React from 'react';
import type { Report } from '@/types/report';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress'; // From shadcn
import { GeneralDataCard } from './mapingReportComponents/GeneralDataCard';
import { DatabaseCard } from './mapingReportComponents/DatabaseCard';
import { TabArea } from './mapingReportComponents/TabArea';
import { WeatherCard } from './mapingReportComponents/WeatherCard';
import { FlightCard } from './mapingReportComponents/FlightCard';
import { AutoDescriptionCard } from './mapingReportComponents/AutoDescriptionCard';
import { GalleryCard } from './mapingReportComponents/GalleryCard';

import ResponsiveResizableLayout from "@/components/report/mapingReportComponents/MappingReportLayout";
import { Card, CardContent, CardTitle } from "@/components/ui/card";


interface Props {
  report: Report;
  onEditClicked: () => void;
}

export function MappingReport({ report, onEditClicked }: Props) {
  // if the status is processing, we can show a progress bar
  const isProcessing = report.status === 'processing' || report.status === 'completed';
  const progress = report.progress ? Math.round(report.progress) : 0;


  return (
    <ResponsiveResizableLayout
      left={
        <div className="flex flex-col gap-4 h-[calc(100vh-90px)]">
          <div className='flex flex-wrap gap-4'>
            <GeneralDataCard report={report} onEditClicked={onEditClicked} />
            <WeatherCard data={report.mapping_report?.weather[0]} onReload={() => { alert("Reload Weather Data"); }} />
            <FlightCard data={report.mapping_report} />
            <AutoDescriptionCard description={report.auto_description} />
          </div>
          <GalleryCard images={report.mapping_report?.images} />
          {/* Add more cards as needed */}
        </div>
      }
      right={
        <TabArea report={report} />
      }
    />

  );
}
