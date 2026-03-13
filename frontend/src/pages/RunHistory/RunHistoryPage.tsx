import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { RunHistoryTable } from '@/components/runs/RunHistoryTable'
import { RunHistoryTimeline } from '@/components/runs/RunHistoryTimeline'
import { RunHistoryCalendar } from '@/components/runs/RunHistoryCalendar'
import { RunDetailDrawer } from '@/components/runs/RunDetailDrawer'
import { useConnectors } from '@/hooks/queries/useConnectors'
import type { RunHistory } from '@/types/api'
import { Calendar, List, Clock, X } from 'lucide-react'

type ViewMode = 'table' | 'timeline' | 'calendar'

export interface RunFilters {
  connectorFilter: string
  statusFilter: string
  dateFrom: string
  dateTo: string
}

const DEFAULT_FILTERS: RunFilters = {
  connectorFilter: 'all',
  statusFilter: 'all',
  dateFrom: '',
  dateTo: '',
}

export default function RunHistoryPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('table')
  const [selectedRun, setSelectedRun] = useState<RunHistory | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [filters, setFilters] = useState<RunFilters>(DEFAULT_FILTERS)
  const [page, setPage] = useState(1)

  const { data: connectors } = useConnectors()

  const updateFilter = (patch: Partial<RunFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch }))
    setPage(1)
  }

  const hasActiveFilters =
    filters.connectorFilter !== DEFAULT_FILTERS.connectorFilter ||
    filters.statusFilter !== DEFAULT_FILTERS.statusFilter ||
    filters.dateFrom !== DEFAULT_FILTERS.dateFrom ||
    filters.dateTo !== DEFAULT_FILTERS.dateTo

  const handleRunClick = (run: RunHistory) => {
    setSelectedRun(run)
    setIsDrawerOpen(true)
  }

  const handleDayClick = (_date: Date) => {
    setViewMode('table')
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Run History</h1>
        <p className="text-muted-foreground mt-2">
          View and monitor connector ingestion runs
        </p>
      </div>

      {/* Filter bar */}
      <div className="grid grid-cols-4 gap-4 p-4 border rounded-lg bg-card items-end">
        <div className="space-y-2">
          <Label>Connector</Label>
          <Select
            value={filters.connectorFilter}
            onValueChange={(value) => updateFilter({ connectorFilter: value })}
          >
            <SelectTrigger>
              <SelectValue placeholder="All connectors" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All connectors</SelectItem>
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
          <Select
            value={filters.statusFilter}
            onValueChange={(value) => updateFilter({ statusFilter: value })}
          >
            <SelectTrigger>
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="running">Running</SelectItem>
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
            value={filters.dateFrom}
            onChange={(e) => updateFilter({ dateFrom: e.target.value })}
          />
        </div>

        <div className="space-y-2">
          <Label>Date To</Label>
          <div className="flex gap-2">
            <Input
              type="date"
              value={filters.dateTo}
              onChange={(e) => updateFilter({ dateTo: e.target.value })}
            />
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setFilters(DEFAULT_FILTERS)
                  setPage(1)
                }}
                className="shrink-0"
              >
                <X className="h-4 w-4" />
                Clear
              </Button>
            )}
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Ingestion Runs</CardTitle>
              <CardDescription>
                Historical record of all connector sync operations
              </CardDescription>
            </div>
            <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as ViewMode)}>
              <TabsList>
                <TabsTrigger value="table" className="gap-2">
                  <List className="h-4 w-4" />
                  Table
                </TabsTrigger>
                <TabsTrigger value="timeline" className="gap-2">
                  <Clock className="h-4 w-4" />
                  Timeline
                </TabsTrigger>
                <TabsTrigger value="calendar" className="gap-2">
                  <Calendar className="h-4 w-4" />
                  Calendar
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
        <CardContent>
          {viewMode === 'table' && (
            <RunHistoryTable
              filters={filters}
              page={page}
              onPageChange={setPage}
              onRowClick={handleRunClick}
            />
          )}
          {viewMode === 'timeline' && (
            <RunHistoryTimeline filters={filters} onRunClick={handleRunClick} />
          )}
          {viewMode === 'calendar' && (
            <RunHistoryCalendar filters={filters} onDayClick={handleDayClick} />
          )}
        </CardContent>
      </Card>

      <RunDetailDrawer
        run={selectedRun}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
      />
    </div>
  )
}
