import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Pencil, Trash2, MapPin } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useUpdateEndpoint, useDeleteEndpoint } from '@/hooks/queries/useEndpoints'
import type { ConnectorEndpoint } from '@/types/api'

interface EndpointCardProps {
  endpoint: ConnectorEndpoint
  connectorId: string
  onEdit: (endpoint: ConnectorEndpoint) => void
}

export function EndpointCard({ endpoint, connectorId, onEdit }: EndpointCardProps) {
  const [deleteOpen, setDeleteOpen] = useState(false)
  const updateEndpoint = useUpdateEndpoint()
  const deleteEndpoint = useDeleteEndpoint()

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: endpoint.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  const handleToggle = (checked: boolean) => {
    updateEndpoint.mutate({
      connectorId,
      endpointId: endpoint.id,
      endpoint: { is_enabled: checked },
    })
  }

  const handleDelete = () => {
    deleteEndpoint.mutate(
      { connectorId, endpointId: endpoint.id },
      { onSuccess: () => setDeleteOpen(false) }
    )
  }

  return (
    <>
      <div
        ref={setNodeRef}
        style={style}
        className={`flex items-center gap-3 rounded-lg border p-4 bg-card ${
          !endpoint.is_enabled ? 'opacity-60' : ''
        }`}
      >
        {/* Drag handle */}
        <button
          className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground touch-none"
          {...attributes}
          {...listeners}
          aria-label="Drag to reorder"
        >
          <GripVertical className="h-4 w-4" />
        </button>

        {/* Endpoint info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm truncate">{endpoint.name}</span>
            {!endpoint.is_enabled && (
              <Badge variant="secondary" className="text-xs shrink-0">
                Disabled
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground truncate">{endpoint.path}</p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 shrink-0">
          <Switch
            checked={endpoint.is_enabled}
            onCheckedChange={handleToggle}
            disabled={updateEndpoint.isPending}
            aria-label={`Toggle ${endpoint.name}`}
          />

          <Button variant="outline" size="sm" asChild>
            <Link to={`/connectors/${connectorId}/endpoints/${endpoint.id}/mappings`}>
              <MapPin className="h-3 w-3 mr-1" />
              Mappings
            </Link>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => onEdit(endpoint)}
            aria-label={`Edit ${endpoint.name}`}
          >
            <Pencil className="h-3 w-3" />
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setDeleteOpen(true)}
            aria-label={`Delete ${endpoint.name}`}
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete endpoint {endpoint.name}?</DialogTitle>
            <DialogDescription>
              This will permanently delete the endpoint and all its field mappings.
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteEndpoint.isPending}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
