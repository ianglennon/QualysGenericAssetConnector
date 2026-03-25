import { useParams } from 'react-router-dom'
import { Skeleton } from '@/components/ui/skeleton'
import { useConnector } from '@/hooks/queries/useConnectors'
import { ChainCanvas } from '@/components/canvas/ChainCanvas'

export function ChainCanvasPage() {
  const { connectorId, canvasId } = useParams<{ connectorId: string; canvasId: string }>()
  const { data: connector, isLoading } = useConnector(connectorId)

  if (isLoading) {
    return (
      <div className="flex flex-col h-full">
        <div className="px-4 py-2 border-b">
          <Skeleton className="h-8 w-64" />
        </div>
        <Skeleton className="flex-1" />
      </div>
    )
  }

  if (!connector || !connectorId) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Connector not found.</p>
      </div>
    )
  }

  return (
    <div className="h-full">
      <ChainCanvas
        connectorId={connectorId}
        connectorName={connector.name}
        canvasId={canvasId}
      />
    </div>
  )
}
