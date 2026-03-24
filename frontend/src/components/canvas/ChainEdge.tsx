import { BaseEdge, getSmoothStepPath, type EdgeProps, type Edge } from '@xyflow/react'
import type { ChainEdgeData } from '@/types/canvas'

export type ChainEdgeType = Edge<ChainEdgeData, 'chain'>

export function ChainEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
}: EdgeProps<ChainEdgeType>) {
  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })
  return (
    <BaseEdge
      id={id}
      path={edgePath}
      style={{ stroke: 'hsl(var(--primary))', strokeWidth: 2 }}
    />
  )
}
