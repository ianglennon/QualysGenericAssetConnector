import { Badge } from '@/components/ui/badge'
import { TableRow, TableCell } from '@/components/ui/table'
import type { StageEntry } from '@/types/api'

const STAGE_DISPLAY_NAMES: Record<string, string> = {
  source_fetch: 'Source Fetch',
  transformation: 'Transformation',
  exclusion: 'Exclusion',
  qualys_submit: 'Qualys Submit',
}

function formatStageDuration(ms: number): string {
  if (ms < 60000) {
    return `${(ms / 1000).toFixed(1)}s`
  }
  const minutes = Math.floor(ms / 60000)
  const seconds = Math.floor((ms % 60000) / 1000)
  return `${minutes}m ${seconds}s`
}

function getStageStatusBadge(status: string) {
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

interface StageSummaryRowProps {
  stage: StageEntry
  isFirstStage: boolean
}

export function StageSummaryRow({ stage, isFirstStage }: StageSummaryRowProps) {
  const delta = stage.records_in > stage.records_out ? stage.records_in - stage.records_out : 0

  return (
    <TableRow>
      <TableCell className="font-medium">
        {STAGE_DISPLAY_NAMES[stage.stage] ?? stage.stage}
      </TableCell>
      <TableCell>{isFirstStage ? '-' : stage.records_in}</TableCell>
      <TableCell>
        {stage.records_out}
        {delta > 0 && (
          <span className="text-destructive ml-1">(-{delta})</span>
        )}
      </TableCell>
      <TableCell>{formatStageDuration(stage.duration_ms)}</TableCell>
      <TableCell>{getStageStatusBadge(stage.status)}</TableCell>
    </TableRow>
  )
}
