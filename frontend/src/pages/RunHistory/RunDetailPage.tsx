import { useParams, Link } from 'react-router-dom'
import { ROUTES } from '@/routes/constants'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ArrowLeft, AlertCircle } from 'lucide-react'
import { useRun } from '@/hooks/queries/useRuns'
import { format } from 'date-fns'
import type { EndpointRunLog } from '@/types/api'

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

  const filterAuthHeaders = (headers: any): any => {
    if (!headers) return headers
    const filtered = { ...headers }
    delete filtered.authorization
    delete filtered.Authorization
    return filtered
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

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="request">Request</TabsTrigger>
          <TabsTrigger value="response">Response</TabsTrigger>
          {run.error_details && <TabsTrigger value="errors">Error Details</TabsTrigger>}
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
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

          {run.endpoint_logs && run.endpoint_logs.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-lg font-semibold">Endpoint Breakdown</h3>
              {[...run.endpoint_logs]
                .sort((a: EndpointRunLog, b: EndpointRunLog) => a.execution_order - b.execution_order)
                .map((log: EndpointRunLog) => (
                  <Card key={log.id}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">
                          {log.endpoint_name || log.endpoint_id}
                        </CardTitle>
                        {getStatusBadge(log.status)}
                      </div>
                      <CardDescription>
                        {log.endpoint_path || 'Unknown path'}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="grid grid-cols-3 gap-4 p-3 border rounded-lg bg-muted/50">
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
                      </div>
                      {log.error_message && (
                        <Alert variant="destructive">
                          <AlertCircle className="h-4 w-4" />
                          <AlertDescription>{log.error_message}</AlertDescription>
                        </Alert>
                      )}
                    </CardContent>
                  </Card>
                ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="request" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Request Payload</CardTitle>
              <CardDescription>Data sent to target API</CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="text-xs p-4 bg-muted rounded-md overflow-auto max-h-96">
                {run.request_payload
                  ? JSON.stringify(run.request_payload, null, 2)
                  : 'No request payload recorded'}
              </pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Request Headers</CardTitle>
              <CardDescription>
                HTTP headers (authorization headers excluded for security)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="text-xs p-4 bg-muted rounded-md overflow-auto max-h-96">
                {run.request_headers
                  ? JSON.stringify(filterAuthHeaders(run.request_headers), null, 2)
                  : 'No request headers recorded'}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="response" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Response Body</CardTitle>
              <CardDescription>Response received from target API</CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="text-xs p-4 bg-muted rounded-md overflow-auto max-h-96">
                {run.response_body
                  ? JSON.stringify(run.response_body, null, 2)
                  : 'No response body recorded'}
              </pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Response Headers</CardTitle>
              <CardDescription>HTTP response headers</CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="text-xs p-4 bg-muted rounded-md overflow-auto max-h-96">
                {run.response_headers
                  ? JSON.stringify(run.response_headers, null, 2)
                  : 'No response headers recorded'}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>

        {run.error_details && (
          <TabsContent value="errors">
            <Card>
              <CardHeader>
                <CardTitle>Error Details</CardTitle>
                <CardDescription>Detailed error information</CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="text-xs p-4 bg-muted rounded-md overflow-auto max-h-96">
                  {JSON.stringify(run.error_details, null, 2)}
                </pre>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
