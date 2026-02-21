import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useRuns } from '@/hooks/queries/useRuns'
import type { RunHistory } from '@/types/api'
import {
  format,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  isSameDay,
  parseISO,
  startOfWeek,
  endOfWeek,
  addMonths,
  subMonths,
} from 'date-fns'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useState } from 'react'

interface RunHistoryCalendarProps {
  onDayClick: (date: Date) => void
}

export const RunHistoryCalendar = ({ onDayClick }: RunHistoryCalendarProps) => {
  const [currentMonth, setCurrentMonth] = useState(new Date())
  
  const monthStart = startOfMonth(currentMonth)
  const monthEnd = endOfMonth(currentMonth)
  const calendarStart = startOfWeek(monthStart)
  const calendarEnd = endOfWeek(monthEnd)

  const { data: runsData, isLoading } = useRuns({
    date_from: format(monthStart, 'yyyy-MM-dd'),
    date_to: format(monthEnd, 'yyyy-MM-dd'),
    size: 1000,
  })

  const calendarDays = eachDayOfInterval({ start: calendarStart, end: calendarEnd })

  const getRunsForDay = (day: Date): RunHistory[] => {
    return (runsData?.items || []).filter((run) =>
      isSameDay(parseISO(run.started_at), day)
    )
  }

  const getStatusCounts = (runs: RunHistory[]) => {
    const counts = { success: 0, partial_success: 0, failed: 0 }
    runs.forEach((run) => {
      if (run.status in counts) {
        counts[run.status as keyof typeof counts]++
      }
    })
    return counts
  }

  if (isLoading) {
    return <Skeleton className="h-96 w-full" />
  }

  return (
    <div className="space-y-4">
      {/* Month navigation */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">
          {format(currentMonth, 'MMMM yyyy')}
        </h3>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentMonth(new Date())}
          >
            Today
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Calendar grid */}
      <div className="border rounded-lg overflow-hidden">
        {/* Day headers */}
        <div className="grid grid-cols-7 border-b bg-muted">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
            <div
              key={day}
              className="p-2 text-center text-sm font-medium text-muted-foreground"
            >
              {day}
            </div>
          ))}
        </div>

        {/* Calendar days */}
        <div className="grid grid-cols-7">
          {calendarDays.map((day) => {
            const runs = getRunsForDay(day)
            const counts = getStatusCounts(runs)
            const isCurrentMonth = day.getMonth() === currentMonth.getMonth()
            const isToday = isSameDay(day, new Date())

            return (
              <button
                key={day.toISOString()}
                onClick={() => onDayClick(day)}
                className={`
                  min-h-[80px] p-2 border-b border-r text-left
                  hover:bg-accent transition-colors
                  ${!isCurrentMonth ? 'bg-muted/30 text-muted-foreground' : ''}
                  ${isToday ? 'bg-primary/5 font-semibold' : ''}
                `}
              >
                <div className="text-sm mb-1">
                  {format(day, 'd')}
                </div>
                {runs.length > 0 && (
                  <div className="space-y-0.5">
                    {counts.success > 0 && (
                      <Badge
                        variant="outline"
                        className="text-xs bg-green-600/10 text-green-700 border-green-600/20"
                      >
                        {counts.success} ✓
                      </Badge>
                    )}
                    {counts.partial_success > 0 && (
                      <Badge
                        variant="outline"
                        className="text-xs bg-yellow-600/10 text-yellow-700 border-yellow-600/20"
                      >
                        {counts.partial_success} ⚠
                      </Badge>
                    )}
                    {counts.failed > 0 && (
                      <Badge
                        variant="outline"
                        className="text-xs bg-red-600/10 text-red-700 border-red-600/20"
                      >
                        {counts.failed} ✗
                      </Badge>
                    )}
                  </div>
                )}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
