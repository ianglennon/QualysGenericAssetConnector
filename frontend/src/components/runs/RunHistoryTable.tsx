import { useState } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useRuns } from '@/hooks/queries/useRuns'
import { useConnectors } from '@/hooks/queries/useConnectors'
import type { RunHistory, RunStatus } from '@/types/api'
import { format } from 'date-fns'

interface RunHistoryTableProps {
  onRowClick: (run: RunHistory) => void
}

export const RunHistoryTable = ({ onRowClick }: RunHistoryTableProps) => {
  const [connectorFilter, setConnectorFilter] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [dateFrom, setDateFrom] = useState<string>('')
  const [dateTo, setDateTo] = useState<string>('')
  const [page, setPage] = useState(1)

  const { data: connectors } = useConnectors()
  const { data: runsData, isLoading } = useRuns({
    connector_id: connectorFilter || undefined,
    status: statusFilter || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    page,
    size: 20,
  })

  const getStatusBadge = (status: RunStatus) => {
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

  const formatDuration = (startedAt: string, endedAt?: string) => {
    if (!endedAt) return '-'
    const start = new Date(startedAt)
    const end = new Date(endedAt)
    const durationMs = end.getTime() - start.getTime()
    const seconds = Math.floor(durationMs / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`
    }
    if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`
    }
    return `${seconds}s`
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="grid grid-cols-4 gap-4 p-4 border rounded-lg bg-card">
        <div className="space-y-2">
          <Label>Connector</Label>
          <Select value={connectorFilter} onValueChange={setConnectorFilter}>
            <SelectTrigger>
              <SelectValue placeholder="All connectors" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All connectors</SelectItem>
              {connectors?.map((connector) => (
                <SelectItem key={connector.id} value={connector.id}>
                  {connector.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Status</Label>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger>
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All statuses</SelectItem>
              <SelectItem value="success">Success</SelectItem>
              <SelectItem value="partial_success">Partial Success</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Date From</Label>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label>Date To</Label>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>
      </div>

      {/* Table */}
      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Connector</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead className="text-right">Fetched</TableHead>
              <TableHead className="text-right">Submitted</TableHead>
              <TableHead className="text-right">Failed</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <>
                {[...Array(5)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(7)].map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-5 w-full" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </>
            ) : runsData?.items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground">
                  No runs found
                </TableCell>
              </TableRow>
            ) : (
              runsData?.items.map((run) => (
                <TableRow
                  key={run.id}
                  className="cursor-pointer hover:bg-accent"
                  onClick={() => onRowClick(run)}
                >
                  <TableCell className="font-medium">
                    {run.connector_name || run.connector_id}
                  </TableCell>
                  <TableCell>{getStatusBadge(run.status)}</TableCell>
                  <TableCell>
                    {format(new Date(run.started_at), 'MMM d, yyyy HH:mm')}
                  </TableCell>
                  <TableCell>
                    {formatDuration(run.started_at, run.ended_at)}
                  </TableCell>
                  <TableCell className="text-right">{run.records_fetched}</TableCell>
                  <TableCell className="text-right">{run.records_submitted}</TableCell>
                  <TableCell className="text-right">
                    {run.records_failed > 0 ? (
                      <span className="text-destructive font-medium">
                        {run.records_failed}
                      </span>
                    ) : (
                      run.records_failed
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {runsData?.total ? `${runsData.total} total runs` : ''}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => p + 1)}
            disabled={!runsData?.cursor && (runsData?.items.length || 0) < 20}
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
