import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { HttpDetailPanel } from './HttpDetailPanel'
import { format } from 'date-fns'
import type { EventEntry, HttpRequestDetail, HttpResponseDetail } from '@/types/api'

const EVENT_TYPE_LABELS: Record<string, string> = {
  api_call: 'API Call',
  transform_decision: 'Transform',
  exclusion_result: 'Exclusion',
  qualys_batch: 'Qualys',
  qualys_rejection: 'Rejection',
}

interface EventTimelineItemProps {
  event: EventEntry
}

export function EventTimelineItem({ event }: EventTimelineItemProps) {
  const [detailOpen, setDetailOpen] = useState(false)

  const hasDetail = event.detail != null && Object.keys(event.detail).length > 0
  const isApiCall = event.event_type === 'api_call'
  const hasHttpDetail = isApiCall && hasDetail && event.detail?.http_request && event.detail?.http_response

  return (
    <div className="py-2">
      <div className="flex items-start gap-3">
        <span className="text-xs font-mono text-muted-foreground whitespace-nowrap mt-0.5">
          {format(new Date(event.timestamp), 'HH:mm:ss.SSS')}
        </span>
        <Badge variant="outline" className="shrink-0">
          {EVENT_TYPE_LABELS[event.event_type] ?? event.event_type}
        </Badge>
        <span className="text-sm flex-1">{event.message}</span>
        {hasDetail && (
          <button
            onClick={() => setDetailOpen(!detailOpen)}
            className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
          >
            {detailOpen ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        )}
      </div>
      {detailOpen && hasDetail && (
        <div className="mt-2 ml-20">
          {hasHttpDetail ? (
            <HttpDetailPanel
              httpRequest={event.detail!.http_request as HttpRequestDetail}
              httpResponse={event.detail!.http_response as HttpResponseDetail}
            />
          ) : (
            <pre className="text-xs font-mono bg-muted p-3 rounded-md overflow-x-auto">
              {JSON.stringify(event.detail, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
