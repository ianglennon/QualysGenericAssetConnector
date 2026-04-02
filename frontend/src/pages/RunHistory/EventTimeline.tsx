import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { EventTimelineItem } from './EventTimelineItem'
import type { EventEntry } from '@/types/api'

interface EventTimelineProps {
  events: EventEntry[]
  totalEvents: number
}

export function EventTimeline({ events, totalEvents }: EventTimelineProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-sm font-medium hover:text-foreground transition-colors py-2"
      >
        {isOpen ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        Detailed Event Timeline ({totalEvents} events)
      </button>
      {isOpen && (
        <div className="border-l-2 border-muted ml-4 pl-4 mt-2">
          {events.map((event) => (
            <EventTimelineItem key={event.id} event={event} />
          ))}
          {totalEvents > events.length && (
            <p className="text-sm text-muted-foreground py-2">
              Showing first {events.length} of {totalEvents} events.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
