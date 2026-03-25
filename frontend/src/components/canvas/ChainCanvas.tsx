// Stub: full implementation provided by phase 44 Plan 02
// This file exists to satisfy TypeScript imports in the parallel worktree.
// The orchestrator merge will replace this with the complete ChainCanvas component.

interface ChainCanvasProps {
  connectorId: string
  connectorName: string
  canvasId?: string
}

export function ChainCanvas({ connectorId: _connectorId, connectorName, canvasId }: ChainCanvasProps) {
  void _connectorId
  return (
    <div className="flex items-center justify-center h-full">
      <p className="text-muted-foreground">
        Canvas editor for connector {connectorName} (canvas: {canvasId ?? 'default'})
      </p>
    </div>
  )
}
