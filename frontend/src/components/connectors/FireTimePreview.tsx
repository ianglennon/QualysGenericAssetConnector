import { addMinutes, addHours, addDays, addWeeks, format, formatDistanceToNow } from 'date-fns'

interface FireTimePreviewProps {
  intervalType: string
  intervalValue: number
}

const INTERVAL_ADDERS = {
  minutes: addMinutes,
  hours: addHours,
  days: addDays,
  weeks: addWeeks,
} as const

function computeFireTimes(type: string, value: number, count = 5): Date[] {
  const adder = INTERVAL_ADDERS[type as keyof typeof INTERVAL_ADDERS]
  if (!adder || !value || value <= 0) return []
  const now = new Date()
  return Array.from({ length: count }, (_, i) => adder(now, value * (i + 1)))
}

export function FireTimePreview({ intervalType, intervalValue }: FireTimePreviewProps) {
  const fireTimes = computeFireTimes(intervalType, intervalValue)

  if (fireTimes.length === 0) return null

  return (
    <div className="space-y-1">
      <p className="text-sm font-semibold">Next scheduled runs</p>
      <ul className="space-y-0.5">
        {fireTimes.map((time, i) => (
          <li key={i} className="text-sm text-muted-foreground">
            {i === 0
              ? `${formatDistanceToNow(time, { addSuffix: true })} (${format(time, 'MMM d, HH:mm')})`
              : format(time, 'MMM d, HH:mm')}
          </li>
        ))}
      </ul>
    </div>
  )
}
