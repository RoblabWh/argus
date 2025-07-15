import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Progress } from '@/components/ui/progress'; // From shadcn
import { Button } from '@/components/ui/button';
import type { Report } from '@/types/report';

interface Props {
    report: Report;
    onEditClicked: () => void;
}

export function GeneralDataCard({ report, onEditClicked }: Props) {
    // if the status is processing, we can show a progress bar
    const isProcessing = report.status === 'processing' || report.status === 'completed';
    const progress = report.progress ? Math.round(report.progress) : 0;


    return (
        <Card className="w-full">
            <CardTitle className="text-lg font-semibold p-4">
                {report.title}
            </CardTitle>
            <CardContent>
                {isProcessing && (
                    <div className="mt-4">
                        <div className="relative pt-1">

                        </div>
                        {((report.status === "processing" || report.status === "preprocessing") && report.progress !== undefined) && (
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
            </CardContent>
        </Card>
    )
}