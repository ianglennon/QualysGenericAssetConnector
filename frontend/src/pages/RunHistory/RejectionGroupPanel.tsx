import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { EventEntry } from '@/types/api'

interface RejectionGroupPanelProps {
  events: EventEntry[]
}

interface RejectionGroup {
  reason: string
  count: number
  recordIds: string[]
}

function groupRejections(events: EventEntry[]): RejectionGroup[] {
  const groups = new Map<string, string[]>()

  for (const event of events) {
    const reason = event.message || 'Unknown reason'
    const recordIds = (event.detail?.record_ids as string[]) ?? []
    if (!groups.has(reason)) {
      groups.set(reason, [])
    }
    groups.get(reason)!.push(...recordIds)
  }

  return Array.from(groups.entries()).map(([reason, recordIds]) => ({
    reason,
    count: recordIds.length || 1,
    recordIds,
  }))
}

function RejectionRow({ group }: { group: RejectionGroup }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border-b last:border-b-0 py-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left text-sm hover:bg-muted/50 rounded px-2 py-1"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0" />
        )}
        <span className="font-medium text-destructive">{group.count} records:</span>
        <span className="truncate">{group.reason}</span>
      </button>
      {expanded && group.recordIds.length > 0 && (
        <div className="max-h-48 overflow-y-auto mt-2 ml-8 p-2 bg-muted rounded-md">
          <div className="font-mono text-xs space-y-0.5">
            {group.recordIds.map((id, idx) => (
              <div key={idx}>{id}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function RejectionGroupPanel({ events }: RejectionGroupPanelProps) {
  if (events.length === 0) return null

  const groups = groupRejections(events)

  return (
    <Card className="bg-destructive/5">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold">Rejection Reasons</CardTitle>
      </CardHeader>
      <CardContent>
        {groups.map((group, idx) => (
          <RejectionRow key={idx} group={group} />
        ))}
      </CardContent>
    </Card>
  )
}
