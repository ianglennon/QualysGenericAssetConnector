import { Badge } from '@/components/ui/badge'
import { format } from 'date-fns'
import type { Connector } from '@/types/api'

interface ScheduleBadgeProps {
  connector: Connector
}

export function ScheduleBadge({ connector }: ScheduleBadgeProps) {
  // D-09: No schedule = omit entirely (return null)
  if (!connector.interval_type) return null

  // D-09: Paused = amber outline badge
  if (!connector.schedule_enabled) {
    return (
      <div className="flex items-center gap-2 mt-2">
        <Badge variant="outline" className="border-amber-500 text-amber-600">
          Paused
        </Badge>
      </div>
    )
  }

  // D-09: Active = green outline badge with interval label + next run
  // Pluralization: "Every 1 hour" vs "Every 2 hours"
  const typeLabel = connector.interval_value === 1
    ? connector.interval_type.slice(0, -1)
    : connector.interval_type
  const label = `Every ${connector.interval_value} ${typeLabel}`

  return (
    <div className="flex items-center gap-2 mt-2">
      <Badge variant="outline" className="border-green-600 text-green-600">
        {label}
      </Badge>
      {connector.next_run_at && (
        <span className="text-xs text-muted-foreground">
          Next: {format(new Date(connector.next_run_at), 'MMM d, HH:mm')}
        </span>
      )}
    </div>
  )
}
