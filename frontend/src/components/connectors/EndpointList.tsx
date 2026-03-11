import { useState, useEffect } from 'react'
import {
  DndContext,
  closestCenter,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { EndpointCard } from './EndpointCard'
import { EndpointForm } from './EndpointForm'
import { useEndpoints, useReorderEndpoints } from '@/hooks/queries/useEndpoints'
import type { ConnectorEndpoint } from '@/types/api'

interface EndpointListProps {
  connectorId: string
}

export function EndpointList({ connectorId }: EndpointListProps) {
  const { data: queryEndpoints, isLoading } = useEndpoints(connectorId)
  const reorderEndpoints = useReorderEndpoints()

  const [endpoints, setEndpoints] = useState<ConnectorEndpoint[]>([])
  const [addOpen, setAddOpen] = useState(false)
  const [editEndpoint, setEditEndpoint] = useState<ConnectorEndpoint | undefined>(undefined)

  // Sync local state from query data
  useEffect(() => {
    if (queryEndpoints) {
      setEndpoints(queryEndpoints)
    }
  }, [queryEndpoints])

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    setEndpoints((prev) => {
      const oldIndex = prev.findIndex((e) => e.id === active.id)
      const newIndex = prev.findIndex((e) => e.id === over.id)
      if (oldIndex === -1 || newIndex === -1) return prev

      const reordered = arrayMove(prev, oldIndex, newIndex)

      // Fire reorder mutation with new order
      reorderEndpoints.mutate({
        connectorId,
        order: reordered.map((e) => e.id),
      })

      return reordered
    })
  }

  const handleEditClose = () => {
    setEditEndpoint(undefined)
  }

  return (
    <div className="space-y-4">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">
          Endpoints ({isLoading ? '...' : endpoints.length})
        </h2>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          <Plus className="h-4 w-4 mr-1" />
          Add Endpoint
        </Button>
      </div>

      {/* Endpoint list or empty state */}
      {!isLoading && endpoints.length === 0 ? (
        <div className="rounded-lg border border-dashed p-10 text-center">
          <p className="text-sm text-muted-foreground mb-4">
            No endpoints configured. Add an endpoint to start collecting data from this source.
          </p>
          <Button onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4 mr-1" />
            Add Endpoint
          </Button>
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={endpoints.map((e) => e.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-2">
              {endpoints.map((endpoint) => (
                <EndpointCard
                  key={endpoint.id}
                  endpoint={endpoint}
                  connectorId={connectorId}
                  onEdit={setEditEndpoint}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {/* Add dialog */}
      <EndpointForm
        connectorId={connectorId}
        open={addOpen}
        onOpenChange={setAddOpen}
      />

      {/* Edit dialog */}
      <EndpointForm
        connectorId={connectorId}
        endpoint={editEndpoint}
        open={!!editEndpoint}
        onOpenChange={(open) => {
          if (!open) handleEditClose()
        }}
      />
    </div>
  )
}
