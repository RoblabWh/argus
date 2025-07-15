import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from '@/components/ui/progress'; // From shadcn
import { Button } from '@/components/ui/button';
import type { Report } from '@/types/report';

interface Props {
    report: Report;
}

export function DatabaseCard({ report }: Props) {


    return (
        <Card className="w-full">
            <CardContent>
                <div className="mt-4 max-h-80 overflow-auto text-sm text-muted-foreground bg-gray-50 dark:bg-gray-800 ">
                    {/* Print every property of the report object */}
                    <pre>{JSON.stringify(report, null, 2)}</pre>
                </div>
            </CardContent>
        </Card>
    )
}