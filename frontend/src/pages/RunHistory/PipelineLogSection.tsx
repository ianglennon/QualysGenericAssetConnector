import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { AlertCircle } from 'lucide-react'
import { useRunEvents } from '@/hooks/queries/useRunEvents'
import { StageSummaryRow } from './StageSummaryRow'
import { RejectionGroupPanel } from './RejectionGroupPanel'
import { EventTimeline } from './EventTimeline'
import type { RunEventsResponse } from '@/types/api'

export const hasFaultDiagnosisData = (
  data: RunEventsResponse | null | undefined
): boolean => !!data && data.total_events > 0

interface PipelineLogSectionProps {
  runId: string
}

export function PipelineLogSection({ runId }: PipelineLogSectionProps) {
  const { data, isLoading, isError } = useRunEvents(runId)

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>
          Failed to load pipeline events. Try refreshing the page. If the problem persists, check that the backend service is running.
        </AlertDescription>
      </Alert>
    )
  }

  if (!data || data.stages.length === 0) {
    return (
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">Pipeline Log</h3>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">No pipeline data</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Pipeline stage data is available for runs started after this feature was enabled. Run a new sync to see stage-by-stage breakdown.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const rejectionEvents = data.events.filter(
    (e) => e.event_type === 'qualys_rejection'
  )

  const hasEvents = data.events.length > 0 || data.total_events > 0
  const hasFaultDiag = data.total_events > 0

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Pipeline Log</h3>

      <Card>
        <CardContent className="pt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Stage</TableHead>
                <TableHead>In</TableHead>
                <TableHead>Out</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.stages.map((stage, idx) => (
                <StageSummaryRow
                  key={stage.stage}
                  stage={stage}
                  isFirstStage={idx === 0}
                />
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {rejectionEvents.length > 0 && (
        <RejectionGroupPanel events={rejectionEvents} />
      )}

      {hasEvents && (
        <>
          <Separator />
          <EventTimeline events={data.events} totalEvents={data.total_events} />
        </>
      )}

      {!hasFaultDiag && (
        <p className="text-sm text-muted-foreground">
          Fault Diagnosis is not enabled for this connector. Enable it in connector settings to capture detailed event logs on the next sync run.
        </p>
      )}
    </div>
  )
}
