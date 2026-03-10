import { useState } from 'react'
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  useReactFlow,
  type Edge,
  type EdgeProps,
} from '@xyflow/react'
import type { MappingEdgeData } from '@/types/canvas'

export type MappingEdgeType = Edge<MappingEdgeData, 'mapping'>

export function MappingEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps<MappingEdgeType>) {
  const { deleteElements } = useReactFlow()
  const [hovered, setHovered] = useState(false)
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{ strokeWidth: hovered ? 2 : 1.5, stroke: 'hsl(var(--primary))' }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className="nodrag nopan flex items-center gap-1"
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          {/* Type badge — display only in Phase 8, clickable in Phase 9 */}
          <span className="px-2 py-0.5 text-xs rounded-full bg-muted border border-border font-medium text-muted-foreground">
            {data?.mappingType ?? 'direct'}
          </span>
          {/* × button — only visible on hover */}
          {hovered && (
            <button
              className="w-4 h-4 flex items-center justify-center rounded-full bg-destructive/10 hover:bg-destructive/20 text-destructive text-xs leading-none"
              onClick={() => deleteElements({ edges: [{ id }] })}
              aria-label="Remove mapping"
            >
              ×
            </button>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  )
}
