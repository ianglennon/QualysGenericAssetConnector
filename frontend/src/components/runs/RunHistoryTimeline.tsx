import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useRuns } from '@/hooks/queries/useRuns'
import type { RunHistory, RunStatus } from '@/types/api'
import { format, parseISO, startOfDay, isSameDay } from 'date-fns'
import { CheckCircle2, AlertCircle, XCircle, Clock } from 'lucide-react'

interface RunFilters {
  connectorFilter: string
  statusFilter: string
  dateFrom: string
  dateTo: string
}

interface RunHistoryTimelineProps {
  filters: RunFilters
  onRunClick: (run: RunHistory) => void
}

export const RunHistoryTimeline = ({ filters, onRunClick }: RunHistoryTimelineProps) => {
  const { data: runsData, isLoading } = useRuns({
    connector_id: filters.connectorFilter !== 'all' ? filters.connectorFilter : undefined,
    status: filters.statusFilter !== 'all' ? filters.statusFilter : undefined,
    date_from: filters.dateFrom || undefined,
    date_to: filters.dateTo || undefined,
    size: 50,
  })

  const getStatusIcon = (status: RunStatus) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="h-5 w-5 text-green-600" />
      case 'partial_success':
        return <AlertCircle className="h-5 w-5 text-yellow-600" />
      case 'failed':
        return <XCircle className="h-5 w-5 text-destructive" />
      default:
        return <Clock className="h-5 w-5 text-muted-foreground" />
    }
  }

  const getStatusBadge = (status: RunStatus) => {
    switch (status) {
      case 'success':
        return <Badge className="bg-green-600">Success</Badge>
      case 'partial_success':
        return <Badge className="bg-yellow-600">Partial</Badge>
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  // Group runs by day
  const groupedRuns: { date: Date; runs: RunHistory[] }[] = []

  runsData?.items.forEach((run) => {
    const runDate = startOfDay(parseISO(run.started_at))
    const existingGroup = groupedRuns.find((group) =>
      isSameDay(group.date, runDate)
    )

    if (existingGroup) {
      existingGroup.runs.push(run)
    } else {
      groupedRuns.push({ date: runDate, runs: [run] })
    }
  })

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-20 w-full" />
          </div>
        ))}
      </div>
    )
  }

  if (!runsData?.items.length) {
    return (
      <div className="text-center text-muted-foreground py-8">
        No runs found
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {groupedRuns.map((group) => (
        <div key={group.date.toISOString()} className="space-y-3">
          <h3 className="text-sm font-semibold text-muted-foreground">
            {format(group.date, 'EEEE, MMMM d, yyyy')}
          </h3>
          <div className="relative pl-8 space-y-4 border-l-2 border-muted">
            {group.runs.map((run) => (
              <div
                key={run.id}
                className="relative cursor-pointer group"
                onClick={() => onRunClick(run)}
              >
                {/* Timeline dot */}
                <div className="absolute -left-[17px] top-1 bg-background p-1">
                  {getStatusIcon(run.status)}
                </div>

                {/* Run card */}
                <div className="ml-4 p-3 border rounded-lg bg-card hover:bg-accent transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium">
                          {run.connector_name || run.connector_id}
                        </span>
                        {getStatusBadge(run.status)}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {format(parseISO(run.started_at), 'h:mm a')}
                        {run.finished_at && (
                          <span className="ml-2">
                            • Duration: {Math.round(
                              (new Date(run.finished_at).getTime() -
                                new Date(run.started_at).getTime()) /
                                1000
                            )}s
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        Base Records: {run.base_records_total ?? run.records_fetched} • Submitted: {run.base_records_submitted ?? run.records_submitted}
                        {(run.base_records_failed ?? run.records_failed) > 0 && (
                          <span className="text-destructive font-medium ml-1">
                            • Failed: {run.base_records_failed ?? run.records_failed}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
