import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RunHistoryTable } from '@/components/runs/RunHistoryTable'
import { RunHistoryTimeline } from '@/components/runs/RunHistoryTimeline'
import { RunHistoryCalendar } from '@/components/runs/RunHistoryCalendar'
import { RunDetailDrawer } from '@/components/runs/RunDetailDrawer'
import type { RunHistory } from '@/types/api'
import { Calendar, List, Clock } from 'lucide-react'

type ViewMode = 'table' | 'timeline' | 'calendar'

export default function RunHistoryPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('table')
  const [selectedRun, setSelectedRun] = useState<RunHistory | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)

  const handleRunClick = (run: RunHistory) => {
    setSelectedRun(run)
    setIsDrawerOpen(true)
  }

  const handleDayClick = (date: Date) => {
    // When clicking a day in calendar view, switch to table view filtered by that day
    console.log('Day clicked:', date)
    // TODO: Could implement day filtering in table view
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
          {viewMode === 'table' && <RunHistoryTable onRowClick={handleRunClick} />}
          {viewMode === 'timeline' && <RunHistoryTimeline onRunClick={handleRunClick} />}
          {viewMode === 'calendar' && <RunHistoryCalendar onDayClick={handleDayClick} />}
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
