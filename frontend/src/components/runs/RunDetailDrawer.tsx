import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ExternalLink, AlertCircle } from 'lucide-react'
import type { RunHistory, RunStatus } from '@/types/api'
import { format } from 'date-fns'
import { Link } from 'react-router-dom'

interface RunDetailDrawerProps {
  run: RunHistory | null
  isOpen: boolean
  onClose: () => void
}

export const RunDetailDrawer = ({ run, isOpen, onClose }: RunDetailDrawerProps) => {
  if (!run) return null

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

  const formatDuration = () => {
    if (!run.ended_at) return 'In progress'
    const start = new Date(run.started_at)
    const end = new Date(run.ended_at)
    const durationMs = end.getTime() - start.getTime()
    const seconds = Math.floor(durationMs / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m ${seconds % 60}s`
    }
    if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`
    }
    return `${seconds}s`
  }

  return (
    <Drawer open={isOpen} onOpenChange={onClose}>
      <DrawerContent>
        <div className="mx-auto w-full max-w-2xl">
          <DrawerHeader>
            <DrawerTitle className="flex items-center gap-2">
              {run.connector_name || run.connector_id}
              {getStatusBadge(run.status)}
            </DrawerTitle>
            <DrawerDescription>
              Run ID: {run.id}
            </DrawerDescription>
          </DrawerHeader>

          <div className="p-4 space-y-4">
            {/* Basic Info */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-sm font-medium text-muted-foreground">Started</div>
                <div className="text-sm">
                  {format(new Date(run.started_at), 'MMM d, yyyy h:mm:ss a')}
                </div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">Duration</div>
                <div className="text-sm">{formatDuration()}</div>
              </div>
            </div>

            {/* Record Counts */}
            <div className="grid grid-cols-3 gap-4 p-4 border rounded-lg bg-muted/50">
              <div className="text-center">
                <div className="text-2xl font-bold">{run.records_fetched}</div>
                <div className="text-xs text-muted-foreground">Fetched</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {run.records_submitted}
                </div>
                <div className="text-xs text-muted-foreground">Submitted</div>
              </div>
              <div className="text-center">
                <div className={`text-2xl font-bold ${run.records_failed > 0 ? 'text-destructive' : ''}`}>
                  {run.records_failed}
                </div>
                <div className="text-xs text-muted-foreground">Failed</div>
              </div>
            </div>

            {/* Error Message */}
            {run.error_message && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription className="mt-2 text-sm">
                  {run.error_message}
                </AlertDescription>
              </Alert>
            )}

            {/* View Full Details Link */}
            <div className="flex justify-center pt-2">
              <Link to={`/runs/${run.id}`} onClick={onClose}>
                <Button variant="outline">
                  <ExternalLink className="h-4 w-4 mr-2" />
                  View Full Details
                </Button>
              </Link>
            </div>
          </div>

          <DrawerFooter>
            <DrawerClose asChild>
              <Button variant="outline">Close</Button>
            </DrawerClose>
          </DrawerFooter>
        </div>
      </DrawerContent>
    </Drawer>
  )
}
