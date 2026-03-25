import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus } from 'lucide-react'
import { useCanvases, useCreateCanvas, useDeleteCanvas, useTriggerCanvasSync } from '@/hooks/queries/useCanvases'
import { useToast } from '@/hooks/use-toast'
import { ROUTES } from '@/routes/constants'
import { CanvasCard } from './CanvasCard'
import { CreateCanvasDialog } from './CreateCanvasDialog'
import { DeleteCanvasDialog } from './DeleteCanvasDialog'
import type { CanvasListItem } from '@/types/canvas'

interface CanvasGridProps {
  connectorId: string
}

export function CanvasGrid({ connectorId }: CanvasGridProps) {
  const { data: canvases, isLoading, isError } = useCanvases(connectorId)
  const createCanvas = useCreateCanvas()
  const deleteCanvas = useDeleteCanvas()
  const triggerSync = useTriggerCanvasSync()
  const navigate = useNavigate()
  const { toast } = useToast()

  const [showCreate, setShowCreate] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<CanvasListItem | null>(null)

  const handleCreate = async (name: string, description?: string) => {
    setCreateError(null)
    try {
      const newCanvas = await createCanvas.mutateAsync({ connectorId, name, description })
      setShowCreate(false)
      navigate(ROUTES.connectorCanvas(connectorId, newCanvas.id))
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: { error_message?: string } } } }
      setCreateError(axiosError.response?.data?.detail?.error_message ?? 'Failed to create canvas')
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteCanvas.mutateAsync({ connectorId, canvasId: deleteTarget.id })
      toast({ title: 'Canvas deleted' })
      setDeleteTarget(null)
    } catch {
      toast({ title: 'Failed to delete canvas', variant: 'destructive' })
    }
  }

  const handleSync = async (canvas: CanvasListItem) => {
    try {
      await triggerSync.mutateAsync({ connectorId, canvasId: canvas.id })
      toast({ title: `Sync started for ${canvas.name}` })
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: { error_message?: string } } } }
      toast({
        title: 'Failed to start sync',
        description: axiosError.response?.data?.detail?.error_message ?? 'An unexpected error occurred',
        variant: 'destructive',
      })
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Canvases</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Canvases</h2>
        <p className="text-sm text-destructive">Failed to load canvases. Check your connection and try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Canvases</h2>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4 mr-2" />
          New Canvas
        </Button>
      </div>

      {canvases && canvases.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {canvases.map((canvas) => (
            <CanvasCard
              key={canvas.id}
              canvas={canvas}
              connectorId={connectorId}
              onDelete={setDeleteTarget}
              onSync={handleSync}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <h3 className="text-base font-semibold">No canvases yet</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Create a canvas to define a data flow from a source API to Qualys.
          </p>
        </div>
      )}

      <CreateCanvasDialog
        open={showCreate}
        onOpenChange={setShowCreate}
        onSubmit={handleCreate}
        isPending={createCanvas.isPending}
        error={createError}
      />

      <DeleteCanvasDialog
        canvas={deleteTarget}
        open={!!deleteTarget}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
        onConfirm={handleDelete}
        isPending={deleteCanvas.isPending}
      />
    </div>
  )
}
