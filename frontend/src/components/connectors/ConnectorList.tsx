import { ConnectorCard } from './ConnectorCard'
import { Skeleton } from '@/components/ui/skeleton'
import type { Connector } from '@/types/api'

interface ConnectorListProps {
  connectors?: Connector[]
  isLoading?: boolean
  onEdit?: (connector: Connector) => void
  onDelete?: (connector: Connector) => void
  onTriggerSync?: (connector: Connector) => void
  syncSuccessId?: string | null
}

export function ConnectorList({
  connectors = [],
  isLoading = false,
  onEdit,
  onDelete,
  onTriggerSync,
  syncSuccessId,
}: ConnectorListProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
    )
  }

  if (connectors.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
        <h3 className="text-lg font-semibold">No connectors yet</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Get started by creating your first connector.
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {connectors.map((connector) => (
        <ConnectorCard
          key={connector.id}
          connector={connector}
          onEdit={onEdit}
          onDelete={onDelete}
          onTriggerSync={onTriggerSync}
          isSyncSucceeded={syncSuccessId === connector.id}
        />
      ))}
    </div>
  )
}
