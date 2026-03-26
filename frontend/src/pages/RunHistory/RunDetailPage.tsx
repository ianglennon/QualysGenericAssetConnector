import { useParams, Link } from 'react-router-dom'
import { ROUTES } from '@/routes/constants'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ArrowLeft, AlertCircle } from 'lucide-react'
import { useRun } from '@/hooks/queries/useRuns'
import { HttpDetailPanel } from './HttpDetailPanel'
import { format } from 'date-fns'
import type { EndpointRunLog } from '@/types/api'

const STAGE_LABELS: Record<string, string> = {
  source_fetch: 'Source Fetch',
  transformation: 'Transformation',
  qualys_submit: 'Qualys Submit',
}

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: run, isLoading } = useRun(id)

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'success':
        return <Badge className="bg-green-600">Success</Badge>
      case 'partial_success':
        return <Badge className="bg-yellow-600">Partial Success</Badge>
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const formatDuration = () => {
    if (!run || !run.finished_at) return 'In progress'
    const start = new Date(run.started_at)
    const end = new Date(run.finished_at)
    const durationMs = end.getTime() - start.getTime()
    const seconds = Math.floor(durationMs / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m ${seconds % 60}s`
    }
    if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`
    }
    return `${seconds}s`
  }

  if (isLoading) {
    return (
      <div className="container mx-auto p-6 space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  if (!run) {
    return (
      <div className="container mx-auto p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Run not found</AlertTitle>
          <AlertDescription>
            The requested run could not be found.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Link to={ROUTES.RUNS}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Run History
          </Button>
        </Link>
      </div>

      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold tracking-tight">
            {run.connector_name || run.connector_id}
          </h1>
          {getStatusBadge(run.status)}
        </div>
        <p className="text-muted-foreground mt-2">Run ID: {run.id}</p>
      </div>

      <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Run Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Started</div>
                  <div className="text-sm mt-1">
                    {format(new Date(run.started_at), 'MMMM d, yyyy h:mm:ss a')}
                  </div>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Duration</div>
                  <div className="text-sm mt-1">{formatDuration()}</div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4 p-4 border rounded-lg bg-muted/50">
                <div className="text-center">
                  <div className="text-3xl font-bold">{run.records_fetched}</div>
                  <div className="text-sm text-muted-foreground">Records Fetched</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-green-600">
                    {run.records_submitted}
                  </div>
                  <div className="text-sm text-muted-foreground">Records Submitted</div>
                </div>
                <div className="text-center">
                  <div
                    className={`text-3xl font-bold ${
                      run.records_failed > 0 ? 'text-destructive' : ''
                    }`}
                  >
                    {run.records_failed}
                  </div>
                  <div className="text-sm text-muted-foreground">Records Failed</div>
                </div>
              </div>

              {run.error_message && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Error Message</AlertTitle>
                  <AlertDescription className="mt-2">
                    {run.error_message}
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>

          {run.endpoint_logs && run.endpoint_logs.length > 0 && (() => {
            const sorted = [...run.endpoint_logs].sort(
              (a: EndpointRunLog, b: EndpointRunLog) => a.execution_order - b.execution_order
            )

            // D-10: Group chain logs by canvas_name for section headers
            const chainLogs = sorted.filter((l: EndpointRunLog) => l.canvas_id != null)
            const flatLogs = sorted.filter((l: EndpointRunLog) => !l.canvas_id)

            const canvasGroups = new Map<string, { name: string; logs: EndpointRunLog[] }>()
            for (const log of chainLogs) {
              const key = log.canvas_id!
              if (!canvasGroups.has(key)) {
                canvasGroups.set(key, { name: log.canvas_name || 'Unknown Canvas', logs: [] })
              }
              canvasGroups.get(key)!.logs.push(log)
            }

            const renderLogCard = (log: EndpointRunLog, indent: boolean) => (
              <div
                key={log.id}
                style={indent ? { marginLeft: (log.depth ?? 0) * 32 } : undefined}
              >
                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base">
                        {log.endpoint_name || log.endpoint_id}
                      </CardTitle>
                      <div className="flex items-center gap-2">
                        {getStatusBadge(log.status)}
                        {log.failure_stage && (
                          <Badge variant="destructive">
                            {STAGE_LABELS[log.failure_stage] ?? log.failure_stage}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <CardDescription>
                      {log.endpoint_path || 'Unknown path'}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className={`grid ${(log.records_filtered ?? 0) > 0 ? 'grid-cols-4' : 'grid-cols-3'} gap-4 p-3 border rounded-lg bg-muted/50`}>
                      <div className="text-center">
                        <div className="text-xl font-bold">{log.records_fetched}</div>
                        <div className="text-xs text-muted-foreground">Records Fetched</div>
                      </div>
                      <div className="text-center">
                        <div className="text-xl font-bold text-green-600">{log.records_submitted}</div>
                        <div className="text-xs text-muted-foreground">Records Submitted</div>
                      </div>
                      <div className="text-center">
                        <div className={`text-xl font-bold ${log.records_failed > 0 ? 'text-destructive' : ''}`}>
                          {log.records_failed}
                        </div>
                        <div className="text-xs text-muted-foreground">Records Failed</div>
                      </div>
                      {(log.records_filtered ?? 0) > 0 && (
                        <div className="text-center">
                          <div className="text-xl font-bold text-muted-foreground">
                            {log.records_filtered}
                          </div>
                          <div className="text-xs text-muted-foreground">Filtered</div>
                        </div>
                      )}
                    </div>
                    {/* D-02: Fan-out summary line */}
                    {log.child_requests_total != null && log.child_requests_total > 0 && (
                      <p className="text-sm text-muted-foreground">
                        {log.child_requests_total - (log.child_requests_failed ?? 0)}/
                        {log.child_requests_total} children succeeded
                        {(log.child_requests_failed ?? 0) > 0 && (
                          <span className="text-destructive font-medium">
                            , {log.child_requests_failed} failed
                          </span>
                        )}
                      </p>
                    )}
                    {log.error_message && (
                      <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>{log.error_message}</AlertDescription>
                      </Alert>
                    )}
                    <HttpDetailPanel
                      httpRequest={log.http_request}
                      httpResponse={log.http_response}
                    />
                  </CardContent>
                </Card>
              </div>
            )

            return (
              <div className="space-y-3">
                <h3 className="text-lg font-semibold">Endpoint Breakdown</h3>
                {/* Canvas-grouped logs with section headers */}
                {Array.from(canvasGroups.entries()).map(([canvasId, group]) => (
                  <div key={canvasId} className="space-y-3">
                    <h4 className="text-base font-semibold border-b pb-2">{group.name}</h4>
                    {group.logs.map((log: EndpointRunLog) => renderLogCard(log, true))}
                  </div>
                ))}
                {/* Flat logs (no canvas) without section headers */}
                {flatLogs.length > 0 && (
                  <div className="space-y-3">
                    {canvasGroups.size > 0 && (
                      <h4 className="text-base font-semibold border-b pb-2">Unassigned Endpoints</h4>
                    )}
                    {flatLogs.map((log: EndpointRunLog) => renderLogCard(log, false))}
                  </div>
                )}
              </div>
            )
          })()}
      </div>
    </div>
  )
}
