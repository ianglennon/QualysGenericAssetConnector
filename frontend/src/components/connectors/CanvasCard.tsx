import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { MoreVertical } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ROUTES } from '@/routes/constants'
import { InlineRename } from './InlineRename'
import { useUpdateCanvas } from '@/hooks/queries/useCanvases'
import { useToast } from '@/hooks/use-toast'
import type { CanvasListItem } from '@/types/canvas'

interface CanvasCardProps {
  canvas: CanvasListItem
  connectorId: string
  onDelete: (canvas: CanvasListItem) => void
  onSync: (canvas: CanvasListItem) => void
}

export function CanvasCard({ canvas, connectorId, onDelete, onSync }: CanvasCardProps) {
  const navigate = useNavigate()
  const updateCanvas = useUpdateCanvas()
  const { toast } = useToast()
  const [isRenaming, setIsRenaming] = useState(false)

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation()
    updateCanvas.mutate(
      { connectorId, canvasId: canvas.id, payload: { is_enabled: !canvas.is_enabled } },
      {
        onError: () => {
          toast({ title: 'Failed to update canvas', description: 'Please try again.', variant: 'destructive' })
        },
      }
    )
  }

  const handleRename = (newName: string) => {
    updateCanvas.mutate(
      { connectorId, canvasId: canvas.id, payload: { name: newName } },
      {
        onSuccess: () => setIsRenaming(false),
        onError: () => {
          toast({ title: 'Failed to rename canvas', description: 'Please try again.', variant: 'destructive' })
          setIsRenaming(false)
        },
      }
    )
  }

  const handleCardClick = () => {
    if (!isRenaming) {
      navigate(ROUTES.connectorCanvas(connectorId, canvas.id))
    }
  }

  const runStatusBadge = () => {
    if (!canvas.last_run_status) return <span className="text-sm text-muted-foreground">Never synced</span>
    switch (canvas.last_run_status) {
      case 'success':
        return <Badge className="bg-green-600">Success</Badge>
      case 'partial_success':
        return <Badge className="bg-yellow-600">Partial</Badge>
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>
      default:
        return <Badge variant="secondary">{canvas.last_run_status}</Badge>
    }
  }

  return (
    <Card
      className={cn(
        'cursor-pointer hover:border-primary/50 transition-colors',
        !canvas.is_enabled && 'opacity-50'
      )}
      onClick={handleCardClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            {isRenaming ? (
              <InlineRename
                value={canvas.name}
                onSave={handleRename}
                onCancel={() => setIsRenaming(false)}
                disabled={updateCanvas.isPending}
              />
            ) : (
              <h3 className="text-base font-semibold truncate">{canvas.name}</h3>
            )}
          </div>
          <div onClick={(e) => e.stopPropagation()}>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="p-1 rounded-md hover:bg-muted" aria-label="Canvas options">
                  <MoreVertical className="h-4 w-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => setIsRenaming(true)}>
                  Rename Canvas
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onSync(canvas)}>
                  Sync this canvas
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-destructive" onClick={() => onDelete(canvas)}>
                  Delete Canvas
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        {canvas.description && (
          <p className="text-sm text-muted-foreground truncate">{canvas.description}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant={canvas.is_enabled ? 'default' : 'secondary'}>
            {canvas.is_enabled ? 'Enabled' : 'Disabled'}
          </Badge>
          <span className="text-sm text-muted-foreground">
            {canvas.endpoint_count} {canvas.endpoint_count === 1 ? 'endpoint' : 'endpoints'}
          </span>
        </div>
        <div className="flex items-center justify-between">
          {runStatusBadge()}
          <div onClick={handleToggle}>
            <Switch
              checked={canvas.is_enabled}
              aria-label={`Toggle ${canvas.name}`}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
